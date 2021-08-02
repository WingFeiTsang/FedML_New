#!/bin/bash

# login to the client 1
# note that "-t -t" cannot be missed
ssh -t -t 192.168.232.129 > ./zRET 2>&1 <<eeooff
cd ./fedml/fedml_performance_grpc
source activate fedml
nohup ./run_fedavg_performance_grpc.sh resnet18_gn fed_cifar100 "./../data/fed_cifar100" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0 > ./runret 2>&1 &
exit
eeooff

sleep 0.5s

ssh -t -t  192.168.232.130 > ./zRET 2>&1 <<eeooff
cd ./fedml/fedml_performance_grpc
source activate fedml
nohup ./run_fedavg_performance_grpc.sh resnet18_gn fed_cifar100 "./../data/fed_cifar100" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0 > ./runret 2>&1 &
exit
eeooff

sleep 2s
#nohup ./run_fedavg_performance_grpc.sh cnn femnist "./../data/FederatedEMNIST/datasets" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0 > ./runret 2>&1 &
sh ./run_fedavg_performance_grpc.sh resnet18_gn fed_cifar100 "./../data/fed_cifar100" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0

#sh ./run_fedavg_performance_grpc.sh cnn femnist "./../data/FederatedEMNIST/datasets" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0
#sh ./run_fedavg_performance_grpc.sh lor mnist "./../data/MNIST" hetero 0.5 2 2 10 adam GRPC 0.1 0.01 10 2 1 2 2 grpc_ipconfig.csv 0
