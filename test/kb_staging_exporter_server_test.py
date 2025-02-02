# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import json  # noqa: F401
import time
import requests  # noqa: F401
import inspect
import shutil
from mock import patch
import hashlib

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint  # noqa: F401

from biokbase.workspace.client import Workspace as workspaceService
from kb_staging_exporter.kb_staging_exporterImpl import kb_staging_exporter
from kb_staging_exporter.kb_staging_exporterServer import MethodContext
from kb_staging_exporter.authclient import KBaseAuth as _KBaseAuth
from kb_staging_exporter.Utils.staging_downloader import staging_downloader
from ReadsUtils.ReadsUtilsClient import ReadsUtils
from AssemblyUtil.AssemblyUtilClient import AssemblyUtil
from GenomeFileUtil.GenomeFileUtilClient import GenomeFileUtil
from ReadsAlignmentUtils.ReadsAlignmentUtilsClient import ReadsAlignmentUtils


class kb_staging_exporterTest(unittest.TestCase):

    READS_FASTQ_MD5 = '68442259e29e856f766bbe38fedd9b30'
    ASSEMLBY_FASTA_MD5 = 'a5cecffc35ef1cf86c6f7a6e1f72066e'
    GENOME_GENBANK_MD5 = '5d6150673c2b0445bf7912ff79ef82c7'
    ALIGNMENT_BAM_MD5 = '96c59589b0ed7338ff27de1881cf40b3'

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_staging_exporter'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_staging_exporter',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL)
        cls.serviceImpl = kb_staging_exporter(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

        cls.ru = ReadsUtils(cls.callback_url)
        cls.au = AssemblyUtil(cls.callback_url)
        cls.gfu = GenomeFileUtil(cls.callback_url)
        cls.rau = ReadsAlignmentUtils(cls.callback_url)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_kb_staging_exporter_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx

    def md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def loadGenome(self):
        if hasattr(self.__class__, 'test_Genome'):
            return self.__class__.test_Genome

        genbank_file_name = 'minimal.gbff'
        genbank_file_path = os.path.join(self.scratch, genbank_file_name)
        shutil.copy(os.path.join('data', genbank_file_name), genbank_file_path)

        genome_object_name = 'test_Genome'
        test_Genome = self.gfu.genbank_to_genome({'file': {'path': genbank_file_path},
                                                  'workspace_name': self.getWsName(),
                                                  'genome_name': genome_object_name,
                                                  'generate_ids_if_needed': 1
                                                  })['genome_ref']

        self.__class__.test_Genome = test_Genome
        print('Loaded Genome: ' + test_Genome)
        return test_Genome

    def loadReads(self):
        if hasattr(self.__class__, 'test_Reads'):
            return self.__class__.test_Reads

        fwd_reads_file_name = 'reads_1.fq'
        fwd_reads_file_path = os.path.join(self.scratch, fwd_reads_file_name)
        shutil.copy(os.path.join('data', fwd_reads_file_name), fwd_reads_file_path)

        rev_reads_file_name = 'reads_2.fq'
        rev_reads_file_path = os.path.join(self.scratch, rev_reads_file_name)
        shutil.copy(os.path.join('data', rev_reads_file_name), rev_reads_file_path)

        reads_object_name = 'test_Reads'
        test_Reads = self.ru.upload_reads({'fwd_file': fwd_reads_file_path,
                                           'rev_file': rev_reads_file_path,
                                           'wsname': self.getWsName(),
                                           'sequencing_tech': 'Unknown',
                                           'name': reads_object_name
                                           })['obj_ref']

        self.__class__.test_Reads = test_Reads
        print('Loaded Reads: ' + test_Reads)
        return test_Reads

    def loadAssembly(self):
        if hasattr(self.__class__, 'test_Assembly'):
            return self.__class__.test_Assembly

        fasta_file_name = 'test_ref.fa'
        fasta_file_path = os.path.join(self.scratch, fasta_file_name)
        shutil.copy(os.path.join('data', fasta_file_name), fasta_file_path)

        assemlby_name = 'test_Assembly'
        test_Assembly = self.au.save_assembly_from_fasta({'file': {'path': fasta_file_path},
                                                          'workspace_name': self.getWsName(),
                                                          'assembly_name': assemlby_name
                                                          })

        self.__class__.test_Assembly = test_Assembly
        print('Loaded Assembly: ' + test_Assembly)
        return test_Assembly

    def loadAlignment(self):
        if hasattr(self.__class__, 'test_Alignment'):
            return self.__class__.test_Alignment

        test_Reads = self.loadReads()
        test_Genome = self.loadGenome()

        alignment_file_name = 'accepted_hits.bam'
        alignment_file_path = os.path.join(self.scratch, alignment_file_name)
        shutil.copy(os.path.join('data', alignment_file_name), alignment_file_path)

        alignment_object_name_1 = 'test_Alignment_1'
        destination_ref = self.getWsName() + '/' + alignment_object_name_1
        test_Alignment = self.rau.upload_alignment({'file_path': alignment_file_path,
                                                    'destination_ref': destination_ref,
                                                    'read_library_ref': test_Reads,
                                                    'condition': 'test_condition_1',
                                                    'library_type': 'single_end',
                                                    'assembly_or_genome_ref': test_Genome
                                                    })['obj_ref']

        self.__class__.test_Alignment = test_Alignment
        print('Loaded Alignment: ' + test_Alignment)
        return test_Alignment

    def start_test(self):
        testname = inspect.stack()[1][3]
        print('\n*** starting test: ' + testname + ' **')

    def fail_export_to_staging(self, params, error, exception=ValueError, contains=False):
        with self.assertRaises(exception) as context:
            self.getImpl().export_to_staging(self.ctx, params)
        if contains:
            self.assertIn(error, str(context.exception.args))
        else:
            self.assertEqual(error, str(context.exception.args[0]))

    def test_bad_params_export_to_staging_fail(self):
        self.start_test()

        invalidate_params = {'missing_input_ref': 'input_ref',
                             'workspace_name': 'workspace_name'}
        error_msg = '"input_ref" parameter is required, but missing'
        self.fail_export_to_staging(invalidate_params, error_msg)

        invalidate_params = {'input_ref': 'input_ref',
                             'missing_workspace_name': 'workspace_name'}
        error_msg = '"workspace_name" parameter is required, but missing'
        self.fail_export_to_staging(invalidate_params, error_msg)

    @patch.object(staging_downloader, "STAGING_USER_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_reads_ok(self):
        self.start_test()

        test_Reads = self.loadReads()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Reads,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        reads_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(reads_files))

        self.assertEqual(len(reads_files), 1)
        reads_file_name = reads_files[0]
        self.assertTrue(reads_file_name.startswith('test_Reads'))
        self.assertEqual(self.md5(os.path.join(ret['result_dir'], reads_file_name)),
                         self.READS_FASTQ_MD5)

    @patch.object(staging_downloader, "STAGING_USER_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_assembly_ok(self):
        self.start_test()

        test_Assembly = self.loadAssembly()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Assembly,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        assembly_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(assembly_files))

        self.assertEqual(len(assembly_files), 1)
        assembly_file_name = assembly_files[0]
        self.assertTrue(assembly_file_name.startswith('test_Assembly'))
        self.assertEqual(self.md5(os.path.join(ret['result_dir'], assembly_file_name)),
                         self.ASSEMLBY_FASTA_MD5)

    @patch.object(staging_downloader, "STAGING_USER_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_genome_ok(self):
        self.start_test()

        test_Genome = self.loadGenome()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Genome,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        genome_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(genome_files))

        self.assertEqual(len(genome_files), 1)
        genome_file_name = genome_files[0]
        self.assertTrue(genome_file_name.startswith('test_Genome'))
        # self.assertEqual(self.md5(os.path.join(ret['result_dir'], genome_file_name)),
        #                  self.GENOME_GENBANK_MD5)

    @patch.object(staging_downloader, "STAGING_GLOBAL_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_genome_gff_ok(self):
        self.start_test()

        test_Genome = self.loadGenome()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Genome,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True,
                  'export_genome': {'export_genome_genbank': 1,
                                    'export_genome_gff': 1}}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        genome_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                self.ctx['user_id'],
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(genome_files))

        self.assertEqual(len(genome_files), 2)

    @patch.object(staging_downloader, "STAGING_GLOBAL_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_alignment_ok(self):
        self.start_test()

        test_Alignment = self.loadAlignment()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Alignment,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        alignment_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                self.ctx['user_id'],
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(alignment_files))

        self.assertEqual(len(alignment_files), 1)
        bam_file_name = alignment_files[0]
        self.assertTrue(bam_file_name.startswith('test_Alignment'))
        self.assertEqual(self.md5(os.path.join(ret['result_dir'], bam_file_name)),
                         self.ALIGNMENT_BAM_MD5)

    @patch.object(staging_downloader, "STAGING_GLOBAL_FILE_PREFIX", new='/kb/module/work/tmp/')
    def test_export_to_staging_alignment_sam_ok(self):
        self.start_test()

        test_Alignment = self.loadAlignment()
        destination_dir = 'test_staging_export'
        params = {'input_ref': test_Alignment,
                  'workspace_name': self.getWsName(),
                  'destination_dir': destination_dir,
                  'generate_report': True,
                  'export_alignment': {'export_alignment_bam': 1,
                                       'export_alignment_sam': 1}}

        ret = self.getImpl().export_to_staging(self.ctx, params)[0]

        alignment_files = os.listdir(ret['result_dir'])

        staging_files = os.listdir(os.path.join('/kb/module/work/tmp/',
                                                self.ctx['user_id'],
                                                destination_dir))
        print('staging files:\n' + '\n'.join(staging_files))
        self.assertTrue(set(staging_files) >= set(alignment_files))

        self.assertEqual(len(alignment_files), 2)
