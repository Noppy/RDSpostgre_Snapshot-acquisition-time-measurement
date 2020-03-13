# RDS_Snapshot-acquisition-time-measurement
Aurora(Posgresql)のスナップショット取得とクロスリージョンコピー時間の計測




# 環境準備
## (1)事前設定
### (1)-(a) 作業環境の準備
下記を準備します。
* bashが利用可能な環境(LinuxやMacの環境)
* gitがインストールされていること
* aws-cliのセットアップ
* AdministratorAccessポリシーが付与され実行可能な、aws-cliのProfileの設定
* [jq](https://stedolan.github.io/jq/)がインストールされていること *DynamoDBデータのExportしCSV変換する時に利用

### (1)-(b)ツールのclone
環境構築様に資源をcloneする
```shell
git clone https://github.com/Noppy/RDS_Snapshot-acquisition-time-measurement.git
cd RDS_Snapshot-acquisition-time-measurement
```

### (1)-(c) CLI実行用の事前準備
これ以降のAWS-CLIで共通で利用するパラメータを環境変数で設定しておきます。
```shell
export PROFILE="<設定したプロファイル名称を指定。デフォルトの場合はdefaultを設定>"
export REGION=ap-northeast-1
```

## (2)CloudFormationによる環境のデプロイ
```shell
KEYNAME="CHANGE_KEY_PAIR_NAME"  #環境に合わせてキーペア名を設定してください。  

#最新のAmazon Linux2のAMI IDを取得します。
AL2_AMIID=$(aws --profile ${PROFILE} --output text \
    ec2 describe-images \
        --owners amazon \
        --filters 'Name=name,Values=amzn2-ami-hvm-2.0.????????.?-x86_64-gp2' \
                  'Name=state,Values=available' \
        --query 'reverse(sort_by(Images, &CreationDate))[:1].ImageId' ) ;

DB_PASSWORD=$(cat /dev/urandom | base64 | fold -w 12 | sed -e 's/[\/\+\=]/0/g' | head -n 1)

ENGIN_VERSION=$(aws --profile ${PROFILE} --output text \
    rds describe-db-engine-versions \
        --engine postgres \
        --db-parameter-group-family postgres11 \
    --query 'reverse(sort_by(DBEngineVersions[].{Ver:EngineVersion}, &Ver))[:1]' )

#スタック作成時に渡すパラメータを作成します。
CFN_STACK_PARAMETERS='
[
  {
    "ParameterKey": "AmiId",
    "ParameterValue": "'"${AL2_AMIID}"'"
  },
  {
    "ParameterKey": "KeyName",
    "ParameterValue": "'"${KEYNAME}"'"
  },
  {
    "ParameterKey": "RdsMasterUserPassword",
    "ParameterValue": "'"${DB_PASSWORD}"'"
  },
  {
    "ParameterKey": "RdsEngineVersion",
    "ParameterValue": "'"${ENGIN_VERSION}"'"
  }
]'

#スタックを作成します
aws --profile ${PROFILE} cloudformation create-stack \
    --stack-name RDS-Snapshot-acquisition-time-measurement \
    --template-body "file://./cfn/Cfn_environment.yaml" \
    --parameters "${CFN_STACK_PARAMETERS}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --timeout-in-minutes 60;
```

## (3)インスタンスへのログイン
```shell
#インスタンスのパブリックIP取得
InstancePubIp=$(aws --profile ${PROFILE} --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`InstancePublicIp`].[OutputValue]')

#インスタンスへのログイン
ssh-add
ssh -A ec2-user@${InstancePubIp}
```

## (4)検証プログラムセットアップ
### (4)-(a) ツールのインストールとAWS CLIのセットアップ
```shell
#ツールのインストール
sudo yum -y install git postgresql python3
curl -o "get-pip.py" "https://bootstrap.pypa.io/get-pip.py" 
sudo python get-pip.py

#psycopg2(PythonのPosgreSQL接続用ライブラリ)インストール
pip3 install --user psycopg2-binary

#bot3インストール
pip3 install --user boto3

# AWS CLIインストール
pip3 install --upgrade --user awscli
echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
. ~/.bashrc

# AWS cli初期設定
Region=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e 's/.$//')
aws configure set region ${Region}
aws configure set output json

#動作確認
aws sts get-caller-identity
```
### (4)-(b) 検証プログラムのclone
```shell
git clone https://github.com/Noppy/RDS_Snapshot-acquisition-time-measurement.git
cd RDS_Snapshot-acquisition-time-measurement
```
### (4)-(c) RDS接続テストとテーブル作成
検証プログラムの中で利用する環境パラメーターは、環境変数でプログラムに渡します。
```shell
PGHOST=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsAddress`].[OutputValue]')

PGPORT=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsPort`].[OutputValue]')

PGDATABASE=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsDBName`].[OutputValue]')

PGUSER=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsUsername`].[OutputValue]')

PGPASSWORD=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsMasterUserPassword`].[OutputValue]')

RDSID=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsId`].[OutputValue]')

DYNAMOTABLE=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`DynamoDBResultTable`].[OutputValue]')

echo -e "PGHOST     = ${PGHOST}\nPGPORT     = ${PGPORT}\nPGDATABASE = ${PGDATABASE}\nPGUSER     = ${PGUSER}\nPGPASSWORD = ${PGPASSWORD}\nRDSID      = ${RDSID}\nDYNAMOTABLE= ${DYNAMOTABLE}"
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD RDSID DYNAMOTABLE

#接続テスト ==> PGUSERのユーザー名が表示されることを確認
psql -c 'select current_user;'

#テーブル作成
./testprogram/CreateTable.sh 
```
### (4)-(c) 補足 PosgreSQLのメンテナンス
```shell
# Tableの内容を削除したい(truncateしたい)
psql -c 'TRUNCATE testtbl01'

# 表のサイズを確認したい
psql -c 'SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database;'

# 表の行数を確認したい
psql -c 'SELECT count(*) from testtbl01'
```

## (5)検証プログラムの実行
### (5)-(a) 環境変数の取り込み
```shell
PGHOST=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsAddress`].[OutputValue]')

PGPORT=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsPort`].[OutputValue]')

PGDATABASE=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsDBName`].[OutputValue]')

PGUSER=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsUsername`].[OutputValue]')

PGPASSWORD=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsMasterUserPassword`].[OutputValue]')

RDSID=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`RdsId`].[OutputValue]')

DYNAMOTABLE=$(aws --output text \
    cloudformation describe-stacks \
        --stack-name RDS-Snapshot-acquisition-time-measurement \
        --query 'Stacks[].Outputs[?OutputKey==`DynamoDBResultTable`].[OutputValue]')

echo -e "PGHOST     = ${PGHOST}\nPGPORT     = ${PGPORT}\nPGDATABASE = ${PGDATABASE}\nPGUSER     = ${PGUSER}\nPGPASSWORD = ${PGPASSWORD}\nRDSID      = ${RDSID}\nDYNAMOTABLE= ${DYNAMOTABLE}"
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD RDSID DYNAMOTABLE
```

### (5)-(b)検証プログラムの実行
```shell
nohup ./testprogram/TestMain.sh &
```
### (5)-(c)検証結果の取得
作業端末で下記スクリプトでDynamoDBから検証データを取得可能です。([jq](https://stedolan.github.io/jq/)が必要です)
CSVファイルは"RdsSnapshotResultDataTable.csv"という名称です。
```shell
./testprogram/export_dynamodb.s
```

### (5)-(b)検証結果の内容
検証結果で取得するデータは以下の通りです。
 * Time: 検証の開始時刻
 * Rows: インサートした行数(1行に128MiBのファイルを１ファイルインサートするので、128MiB * Rowsがインサートしたデータ量)
 * StorageSizeDelta: CloudWatchメトリクスで取得したインサート前後のストレージ空き容量の差分(ただしあまり有益な情報は取れなかった)
 * InsertDataStartTime: DBへのインサートプログラム開始時刻
 * InsertDataFinishTime: DBへのインサートプログラム終了時刻
 * InsertDataTimeDelta: DBへのインサートプログラム実行時間(秒)
 * CreateSnapStartTime: DBスナップショット作成開始時刻(API実行時刻)
 * CreateSnapFinishTime: DBスナップショット作成完了時刻(Statusがavailableになった時間)
 * CreateSnapTimeDelta: DBスナップショット作成時間(秒)
 * CopySnapStartTime: DBスナップショットの別リージョンへのコピー開始時刻(API実行時刻)
 * CopySnapFinishTime: DBスナップショットの別リージョンへのコピー完了時刻(Statusがavailableになった時間)
 * CopySnapTimeDelta: DBスナップショットの別リージョンへのコピー時間(秒)



