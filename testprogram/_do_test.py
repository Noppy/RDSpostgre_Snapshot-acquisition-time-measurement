#!/bin/env python3
# -*- coding: utf-8 -*-
#
#  _do_test.py
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
import time
import argparse
import boto3
import subprocess
import json


#parameter
insert_prg  = './testprogram/InsertBinaryData_Client.py'
table_name  = 'testtbl01'


# Global values
start_number_of_row = 0
end_number_of_row   = 0


def get_args():
    parser = argparse.ArgumentParser(
        description='Test Core')

    parser.add_argument('-d','--debug',
        action='store_true',
        default=False,
        required=False,
        help='debug mode')

    parser.add_argument('-p','--parallel',
        action='store',
        type=int,
        required=True,
        help='Number of Parallel')

    parser.add_argument('-f','--file',
        action='store',
        type=str,
        required=True,
        help='file path')

    parser.add_argument('-D','--Dst',
        action='store',
        type=str,
        required=True,
        help='Destination region code')

    parser.add_argument('rows',
        type=int,
        nargs='+',
        help='Number of insert rows')

    return( parser.parse_args() )

def get_db_freediskmetrics(args):

    clw = boto3.client('cloudwatch')
    DbId = os.environ.get('RDSID')

    ret = clw.get_metric_statistics(
        Namespace  = 'AWS/RDS',
        MetricName = 'FreeStorageSpace',
        Dimensions = [ { 'Name': 'DBInstanceIdentifier', 'Value': DbId } ],
        Period     = 60,
        Statistics = [ 'Average' ],
        StartTime  = datetime.datetime.now() - datetime.timedelta(minutes=5),
        EndTime    = datetime.datetime.now() )

    #Return
    return( ret['Datapoints'][0]['Average'] )

def create_snap(args, snap_name):

    rds = boto3.client('rds')
    DbId = os.environ.get('RDSID')

    #create snapshot
    ret = rds.create_db_snapshot(
        DBInstanceIdentifier = DbId,
        DBSnapshotIdentifier = snap_name )
    DBSnapshotArn = ret['DBSnapshot']['DBSnapshotArn']

    #wait
    while True:
        ret = rds.describe_db_snapshots(
            DBSnapshotIdentifier = snap_name )
        if args.debug:
            print( ret['DBSnapshots'][0]['Status'] )
        if ret['DBSnapshots'][0]['Status'] == 'available':
            break

        #sleep
        time.sleep(1)

    #finish
    if args.debug:
        print('Done')
    return(DBSnapshotArn)

def copy_snap(args, snap_name, DBSnapshotArn, myregion):
    rds = boto3.client('rds', region_name = args.Dst)
    DbId = os.environ.get('RDSID')
    
    # Get KeyID
    kms = boto3.client('kms', region_name = args.Dst)
    ret = kms.describe_key( KeyId = 'alias/aws/rds' )
    keyid = ret['KeyMetadata']['Arn']

    #Copy snapshot
    ret = rds.copy_db_snapshot(
        SourceDBSnapshotIdentifier = DBSnapshotArn,
        TargetDBSnapshotIdentifier = snap_name,
        SourceRegion = myregion,
        KmsKeyId = 'ddbe8378-2005-4a67-9f6e-82447cda9760' )

    #wait
    while True:
        ret = rds.describe_db_snapshots(
            DBSnapshotIdentifier = snap_name )
        if args.debug:
            print( ret['DBSnapshots'][0]['Status'] )
        if ret['DBSnapshots'][0]['Status'] == 'available':
            break

        #sleep
        time.sleep(1)

    #finish
    if args.debug:
        print('Done')
    return


def truncate_tlb():
    result = subprocess.run( ('psql', '-c', 'TRUNCATE {}'.format(table_name)) )
    return

def do_test(args,myregion):

    #call global value
    global start_number_of_row
    global end_number_of_row

    #loop
    for rows in args.rows:
        # Initialize
        print('Insert {} rows'.format(rows))
        end_number_of_row = start_number_of_row + rows

        # Initial snapshot
        snap_name = 'RdsTest-Snapshot-{:08d}-{}'.format(rows, int(datetime.datetime.timestamp(datetime.datetime.now())) )
        if args.debug:
            print(snap_name)
        create_snap(args, snap_name)

        # Insertdata into Posgresql
        print("Insert rows>>>>>")
        storage_initial_size   = get_db_freediskmetrics(args)
        insert_data_start_time = datetime.datetime.now()
        print("Insert rows: Start:  {}".format(insert_data_start_time))
        result = subprocess.run( (insert_prg, '-n', str(start_number_of_row), '-r', str(end_number_of_row), '-p', str(args.parallel), '-f', args.file) )
        insert_data_finish_time = datetime.datetime.now()
        time.sleep(60)
        storage_finish_size   = get_db_freediskmetrics(args)
        print("Insert rows: Finish: {}".format(insert_data_finish_time))

        # Create snapshot
        print("Create snapshot>>>>>")
        snap_name = 'RdsTest-Snapshot-{:08d}-{}'.format(rows, int(datetime.datetime.timestamp(datetime.datetime.now())) )
        if args.debug:
            print(snap_name)
        create_snap_start_time = datetime.datetime.now()
        print("CreateSnapshots: Start:  {}".format(create_snap_start_time))
        DBSnapshotArn = create_snap(args, snap_name)
        create_snap_finish_time = datetime.datetime.now()
        print("CreateSnapshots: Finish: {}".format(create_snap_finish_time))

        # Copy snapshot
        print("Copy snapshot>>>>>")
        copy_snap_start_time = datetime.datetime.now()
        print("CopySnapshots: Start:  {}".format(copy_snap_start_time))
        copy_snap(args, snap_name, DBSnapshotArn, myregion)
        copy_snap_finish_time = datetime.datetime.now()
        print("CopySnapshots: finish: {}".format(copy_snap_finish_time))

        #Calculate Results
        storage_size_delta     = int(storage_finish_size     - storage_initial_size)
        insert_data_time_delta = insert_data_finish_time - insert_data_start_time
        create_snap_time_delta = create_snap_finish_time - create_snap_start_time
        copy_snap_time_delta   = copy_snap_finish_time   - copy_snap_start_time

        #Write Result to DynamoDB
        tablename = os.environ.get('DYNAMOTABLE')
        dynamodb = boto3.client('dynamodb')

        itemDic = {
            'Time': {'S': datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')},
            'Rows': {'N': str(rows) },
            'StorageSizeDelta':     {'N': str(storage_size_delta) },
            'InsertDataStartTime':  {'S': insert_data_start_time.strftime('%Y/%m/%d %H:%M:%S')},
            'InsertDataFinishTime': {'S': insert_data_finish_time.strftime('%Y/%m/%d %H:%M:%S')},
            'InsertDataTimeDelta':  {'N': str(insert_data_time_delta.total_seconds()) },
            'CreateSnapStartTime':  {'S': create_snap_start_time.strftime('%Y/%m/%d %H:%M:%S')},
            'CreateSnapFinishTime': {'S': create_snap_finish_time.strftime('%Y/%m/%d %H:%M:%S')},
            'CreateSnapTimeDelta':  {'N': str(create_snap_time_delta.total_seconds()) },
            'CopySnapStartTime':    {'S': copy_snap_start_time.strftime('%Y/%m/%d %H:%M:%S')},
            'CopySnapFinishTime':   {'S': copy_snap_finish_time.strftime('%Y/%m/%d %H:%M:%S')},
            'CopySnapTimeDelta':    {'N': str(copy_snap_time_delta.total_seconds()) }
        }
        ret = dynamodb.put_item(
            TableName = tablename,
            Item = itemDic
        )


        # Finish
        start_number_of_row = end_number_of_row + 1
        time.sleep(1)

    #Post-processing
    print("Trancate data")
    truncate_tlb()

    return


if __name__ == "__main__":

    args = get_args()
    myregion = boto3.session.Session().region_name
    do_test(args,myregion)

