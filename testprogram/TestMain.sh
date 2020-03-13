#!/bin/sh

Prallel=10
rows="80 400 800 1600 4000" #128MiB/ファイルで、 10GiB, 50GiB, 100GiB, 200GiB, 500GiB

filename=dummy_128MiB.dat
DestRegion=ap-northeast-3
TestTimes=2

TABLE_NAME='testtbl01'

#PosgreSQLにインサートするバイナリーデータを生成する。
#データは、128MB/ファイルで作成し、圧縮や重複排除の効果を回避するため乱数から生成する。
dd if=/dev/urandom of=${filename} bs=4096 count=32768

#DBのテーブルTrancate
psql -c "truncate ${TABLE_NAME}"

#テストプログラムの実行
for i in $(seq 0 ${TestTimes})
do
    echo "<<<<<<Test n=${i} >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    ./testprogram/_do_test.py -p ${Prallel} -f ${filename} -D ${DestRegion} ${rows}
done

echo 'ALL Test Programs are done!!!'
