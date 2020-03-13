#!/bin/sh

#MPosgreSQL設定
#環境変数で、PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD、が設定されている前提

table_name='testtbl01'

#clear table
psql -c "CREATE TABLE ${table_name} (file_id integer, file_body bytea, PRIMARY KEY(file_id), UNIQUE(file_id) );"
psql -c '\dt'
echo "ALL COMPLETED!!!!"