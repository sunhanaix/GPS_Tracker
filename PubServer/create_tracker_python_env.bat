rem 创建一个是python 3.13版本的python环境，命名为iot_env
conda create -n iot_env -c conda-forge python=3.13

rem 把iot_env改名为iot_tracker_env
conda rename -n iot_env iot_tracker_env

rem 查看当前有哪些创建好了的env
conda env list

rem 激活指定环境
conda activate iot_tracker_env