
from enum import IntEnum

class TaskStatus(IntEnum):
    Creating=0
    CreateFail=1
    Running=2
    Successed=3
    Stop=4       #user stop
    AdminStop=5  #admin stop
    Failed=6     #execute failed
    Unkonw=7  #query task not exist, query task not belong to query user
    
    def __str__(self):
        # 返回枚举成员的名称（如 "Creating"、"Successed" 等）
        return self.name

FigmaDefaultTItle = "DefaultTItle"


MaxUserRunningTask = 5


AdminUser="ByteD2CAdmin"
AdminVerify="ByteD2CAdminVerify"


VersionUpgrade = False

# 连接配置
DB_CONFIG = {
    'user': 'zhoubo.deskid',
    'database': 'd2c_task_db',
    'db': 'd2c_task_db',
    'db_psm':'toutiao.mysql.d2c_task_db_write',
    'charset': 'utf8mb4'
}

# 连接配置#For local verification of the code.
DB_CONFIG_LOCAL = {
    'host': 'localhost',
    'database': 'd2c_task_db_local',
    'user': 'root',
    'password': 'ByteHua!',
    'charset': 'utf8mb4'
}

#config for different db to ensure generate task_id unique
SNOW_CONFIG = {
    'worker_id': 1,
    'data_center_id': 1
}

# config for coder retry
MAXCoderRetry = 6

# config for valid compose code length
MINValidComposeCodeLength = 700

# config for recursion limit
RecursionLimit = 60

# config for evaluate threshold
EvaluateThreshold = 0.0

OUTPUT_DIR="/tmp/d2c_task_output"

# Whether to enable Figma request caching.
# Set to True in test/staging environments to reduce Figma API calls and speed up tests.
# Must be False in production to ensure the latest design files are always fetched.
FIGMA_REQUEST_CACHE = False

Package_Declaration = "package com.example.myapplication"

FigmaSampleUrl= "https://www.figma.com/design/T5UGp5w1e4Re7Y1ePsLoqB/D2C-Benchmark?node-id=69-2157&t=OxJmcfPw7ZZZmavD-4" #"https://www.figma.com/design/T5UGp5w1e4Re7Y1ePsLoqB/D2C-Benchmark?node-id=1-166&t=kMsYMoAYmqy1S6Cm-4" #"https://www.figma.com/design/4VPgbnqRBmEgAyFrz75nNZ/Mediun_Schedule?node-id=0-1&p=f&t=MDCzFXi2duxjOoeX-0"# "https://www.figma.com/design/NDhYpgHZiCs8euNGEt4s7m/D2C-figma-demo?node-id=1-465&t=6c12q9vIPu42nUqq-0" # "https://www.figma.com/design/CP80TPBxJhPIYZe7wrVKu6/Medium_Order?node-id=0-8&t=2XRvc9auNmXNZLrl-4" # 
FigmaSampleToken="figd_jJl4EiVnFY9iP_KStuxg2UoprJeMYnA44YH-uMJy" #"figd_eNJI1is631HtTIoIclB0vfcwlULZVM9XGisGIQPn" # "figd_NOvj1PfYuUFr2L-S_gEZuXf7H519MjWk3uAQjmWO" # 