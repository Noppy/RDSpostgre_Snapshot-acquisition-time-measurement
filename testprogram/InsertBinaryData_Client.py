#!/bin/env python3
# -*- coding: utf-8 -*-
#
#  InsertBinaryData_Client.py
#  ======
#  Copyright (C) 2019 n.fujita
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
from __future__ import print_function

import psycopg2
import sys
import os
import datetime
import threading
import queue
import argparse

table_name='testtbl01'
field_name_id='file_id'
field_name_body='file_body'

def get_args():
    parser = argparse.ArgumentParser(
        description='Insert Binary Data to PosgreSQL Database')

    parser.add_argument('-n','--executeNo',
        action='store',
        type=int,
        required=True,
        help='Execution number')

    parser.add_argument('-p','--parallel',
        action='store',
        type=int,
        required=True,
        help='Number of Parallel')

    parser.add_argument('-r','--rows',
        action='store',
        type=int,
        required=True,
        help='Number of inserted rows')

    parser.add_argument('-f','--file',
        action='store',
        type=str,
        required=True,
        help='file path')

    return( parser.parse_args() )

def print_status(executecount, parallelCount,ExecuteNo):
    date = datetime.datetime.now()
    rows = executecount // parallelCount
    print("{} : Commit {} rows (ExecuteNo {})".format(date, rows, ExecuteNo))

def insertBLOB(executeNo, parallelCount, insertCount, fileName, ThreadNo, ret):
    try:
        # DB Connect
        connection = psycopg2.connect(
            host=os.environ.get('PGHOST'),
            port=int(os.environ.get('PGPORT')),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'), 
            database=os.environ.get('PGDATABASE') )
        cursor = connection.cursor()

        # Read a file
        filedata = open( fileName, 'rb').read()
        psyimage = psycopg2.Binary(filedata)

        # Create query string
        query = "INSERT INTO {0}({1},{2}) VALUES(%s, %s)".format(table_name,field_name_id,field_name_body)
        #print(query)

        # record starting time
        first_time = datetime.datetime.now()

        count = 0
        for executecount in range(executeNo, insertCount+1, parallelCount):
        
            # Insert Operation
            #print("executeNo={},  executecont={}".format(executeNo, executecount))
            cursor.execute(query, (executecount, psyimage) )
            count += 1
         
            connection.commit()
            print_status(executecount, parallelCount, executeNo)

        connection.commit()

        #last 
        last_time = datetime.datetime.now()
        
        #print result 
        delta = last_time - first_time
        print("ThreadNo: {}, ExecutionTime(sec): {}, NumberOfInsertFiles: {},Start: {}, Finish: {}".format( ThreadNo, delta.total_seconds(), count, first_time, last_time ) )

    except Exception as error :
        connection.rollback()
        print("Failed!!:{}".format(error))

    finally:
        # closing database connection.
        if connection:
            # Close cursor
            cursor.close()
            #print("Cursor is closed.")
            connection.close()
            #print("Connection is closed.")

    ret.put(count)



def Launch_insertBLOB(executeNo, parallelCount, insertCount, fileName):

    threads = []
    ret = queue.Queue()
    # creat threads
    for i in range(0, parallelCount):
        t = threading.Thread(target=insertBLOB, args=(executeNo+i,  parallelCount, insertCount, fileName, i, ret))
        threads.append(t)
        print("Run Thread No={}".format(i))

    # record starting time
    first_time = datetime.datetime.now()

    # start threads
    for t in threads:
        t.start()

    # wait threads
    for t in threads:
        t.join()
     
    #last 
    last_time = datetime.datetime.now()
       
    #calclate the result
    delta = last_time - first_time
    count=0
    while True:
        if ret.empty():
            break
        else:
            count += ret.get()

    #print the result
    print("ALL_ExecutionTime(sec):{}".format( delta.total_seconds() ))
    print("ALL_NumberOfInsertFiles:{}".format( count ))
    print("ALL_Start:{}".format( first_time ))
    print("ALL_Finish:{}".format( last_time ))
        
if __name__ == "__main__":

    args = get_args()
    executeNo     = args.executeNo
    parallelCount = args.parallel
    insertCount   = args.rows
    fileName      = args.file

    Launch_insertBLOB(executeNo, parallelCount, insertCount, fileName)