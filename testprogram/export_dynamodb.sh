#!/bin/sh

#dynamodb
DynamodbTable='RdsSnapshotResultDataTable'
csvfile="${DynamodbTable}.csv"

# export from dynamodb
echo '"Time","Rows","StorageSizeDelta","InsertDataStartTime","InsertDataFinishTime","InsertDataTimeDelta","CreateSnapStartTime","CreateSnapFinishTime","CreateSnapTimeDelta","CopySnapStartTime","CopySnapFinishTime","CopySnapTimeDelta"' > ${csvfile}

aws --output json dynamodb scan --table-name ${DynamodbTable} | jq -r -c '
        .Items[] | [
            .Time.S,
            .Rows.N,
            .StorageSizeDelta.N,
            .InsertDataStartTime.S,
            .InsertDataFinishTime.S,
            .InsertDataTimeDelta.N,
            .CreateSnapStartTime.S,
            .CreateSnapFinishTime.S,
            .CreateSnapTimeDelta.N,
            .CopySnapStartTime.S,
            .CopySnapFinishTime.S,
            .CopySnapTimeDelta.N
        ] | @csv'  >> ${csvfile}
