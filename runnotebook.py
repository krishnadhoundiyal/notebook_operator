import glob
import logging
import os
import subprocess
import sys
import time

from abc import ABC, abstractmethod
from packaging import version
from typing import Optional, Any, Type, TypeVar
from urllib.parse import urlparse
import minio
import argparse
# Inputs and Outputs separator character.  If updated,
# same-named variable in _notebook_op.py must be updated!
INOUT_SEPARATOR = ';'
logger = logging.getLogger('explorer')
T = TypeVar('T', bound='FileOpBase')

class FileOpBase(ABC):
    filepath=None
    @classmethod
    def factory_method(cls:Type[T], **kwargs)-> T:
        filepath = kwargs['filepath']
        if '.ipynb' in filepath:
            return NotebookFileOp(**kwargs)
        elif '.py' in filepath:
            return PythonFileOp(**kwargs)
        else:
            raise ValueError('Unsupported file type: {}'.format(filepath))
    def __init__(self,**kwargs:Any)->None:
        self.filepath= kwargs["filepath"]
        self.input_params = kwargs
        self.cos_endpoint = urlparse(self.input_params.get('endpoint'))
        self.cos_bucket = self.input_params.get("bucket")
        self.cos_client = minio.Minio(self.cos_endpoint,
                                      access_key=os.getenv('ENV_ACCESS_ID'),
                                      secret_key=os.getenv('ENV_SECRET_ID',)
                                      )

    @abstractmethod
    def execute(self):
        """Override this behavious in the sub-class - based on type of notebook"""
        raise NotImplementedError("Method 'execut()' should be implemented in the derived class")
    def process_dependencies(self):
        """Downloads all the dependent notebook/python books"""
        archive = self.input_params.get('archive')
    def get_file_from_object_storage(self,file:str)->None:
        """Utility to download the file"""
        object_to_get = self.get_object_storage_filename(file)
        self.cos_client.fget_object(bucket_name=self.cos_bucket,
                                    object_name=object_to_get,
                                    file_path=file
                                    )

    def get_object_storage_filename(self,filename:str)->str:
        return os.path.join(self.input_params.get("directory",","),filename)

class Utility(object):
    global pipeline_name
    @classmethod
    def parse_arguments(cls,args)->dict:
        logger.debug("Parsing Arguments.....")
        parser = argparse.ArgumentParser()
        parser.add_argument('-e','--endpoint',dest='endpoint',required=True,help="Cloud Storage EndPoint")
        parser.add_argument('-b','--bucket',dest='bucket',help='Cloud Storage bucket',required=True)
        parser.add_argument('-d','--directory',dest='directory',required=True,help='Directory in Cloud where Storage is located')
        parser.add_argument('-f','--file',dest='filepath',required=True,help='File to be executed')
        parser.add_argument('-o', '--outputs', dest="outputs", help='Files to output to object store', required=False)
        parser.add_argument('-i', '--inputs', dest="inputs", help='Files to pull in from parent node', required=False)
        parser.add_argument('-s', '--scrapbook', dest="scrapbook", help='Store Scrapes', required=True)
        parsed_args = vars(parser.parse_args(args))
        pipeline_name = parsed_args.get('cos-directory')
        return parsed_args
    @classmethod
    def log_operation_info(cls,action:str)->None:
        logger.info(f"'{pipeline_name}':'{action}'")
        return None
def main():
    # Configure logger format, level
    logging.basicConfig(format='[%(levelname)1.1s %(asctime)s.%(msecs).03d] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)
    # Setup packages and gather arguments
    input_params = Utility.parse_arguments(sys.argv[1:])
    Utility.log_operation_info("starting operation")

    # Create the appropriate instance, process dependencies and execute the operation
    file_op = FileOpBase.get_instance(**input_params)

    file_op.process_dependencies()

    file_op.execute()
    Utility.log_operation_info("operation completed")
if __name__ == '__main__':
    main()