import logging

from typing import List
from concurrent import futures
import threading

import grpc
import time,os
from ..gRPC import grpc_comm_manager_pb2_grpc, grpc_comm_manager_pb2

lock = threading.Lock()

from fedml.fedml_core.distributed.communication.base_com_manager import BaseCommunicationManager
from fedml.fedml_core.distributed.communication.message import Message
from fedml.fedml_core.distributed.communication.observer import Observer
from fedml.fedml_core.distributed.communication.gRPC.grpc_server_and_client import gRPCCOMMServicer
from fedml.fedml_api.distributed.fedavg.utils import transform_tensor_to_list
from fedml.fedml_api.distributed.utils.ip_config_utils import build_ip_table


class GRPCCommManager(BaseCommunicationManager):
    def __init__(self, host, port, ip_config_path, topic='fedml', client_id=0, client_num=0):
        # host is the ip address of server
        self.host = host
        self.port = str(port)
        self._topic = topic
        self.client_id = client_id
        self.client_num = client_num
        self._observers: List[Observer] = []

        self.grpc_server = None
        self.grpc_service = None
        self.ip_config = None

        self.opts = [('grpc.max_send_message_length', 100 * 1024 * 1024),
                     ('grpc.max_receive_message_length', 100 * 1024 * 1024), ('grpc.enable_http_proxy', 0)]

        if client_id == 0:
            self.node_type = "server"
            self.init_server_communication()
        else:
            self.node_type = "client"
            self.init_client_communication()

        self.ip_config = build_ip_table(ip_config_path)
        self.is_running = True
        logging.info("Communication is started with port " + str(port))

    def init_server_communication(self):
        # collecting local parameters from clients
        # staring collecting services at the server
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.client_num), options=self.opts)
        logging.info(self.host +":" +self.port)
        self.grpc_service = gRPCCOMMServicer(self.host, self.port, self.client_num, self.client_id)
        grpc_comm_manager_pb2_grpc.add_gRPCCommManagerServicer_to_server(
            self.grpc_service,
            self.grpc_server
        )

        # starts a grpc_server on local machine using ip address $host
        #self.grpc_server.add_insecure_port("{}:{}".format(self.host, self.port))
        self.grpc_server.add_insecure_port("{}:{}".format(self.host, self.port))
        self.grpc_server.start()
        logging.info("server started. Listening on port " + str(self.port))

    def init_client_communication(self):
        # downloading global parameters from server
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=1), options=self.opts)
        self.grpc_service = gRPCCOMMServicer(self.host, self.port, self.client_num, self.client_id)
        grpc_comm_manager_pb2_grpc.add_gRPCCommManagerServicer_to_server(
            self.grpc_service,
            self.grpc_server
        )

        # starts a grpc_server on local machine using ip address $host
        self.grpc_server.add_insecure_port("{}:{}".format(self.host, self.port))
        self.grpc_server.start()
        logging.info("client " + str(self.host) + " is started. Listening on port " + str(self.port))

    def send_message(self, msg: Message):
        payload = msg.to_json()
        receiver_id = msg.get_receiver_id()

        # lookup ip of receiver from self.ip_config table
        receiver_ip = self.ip_config[str(receiver_id)]
        channel_url = '{}:{}'.format(receiver_ip, str(50000 + receiver_id))

        logging.info(channel_url)
        channel = grpc.insecure_channel(channel_url, options=self.opts)
        stub = grpc_comm_manager_pb2_grpc.gRPCCommManagerStub(channel)

        request = grpc_comm_manager_pb2.CommRequest()
        request.server_id = self.client_id
        request.message = payload
        logging.info("Server sends msg to port " + str(50000 + receiver_id))
        responose = stub.sendMessage(request)
        logging.info(responose)
        channel.close()
        logging.info("Mesag is send!~~~~")

    def add_observer(self, observer: Observer):
        self._observers.append(observer)

    def remove_observer(self, observer: Observer):
        self._observers.remove(observer)

    def handle_receive_message(self):
        thread = threading.Thread(target=self.message_handling_subroutine)
        thread.start()

    def message_handling_subroutine(self):
        while self.is_running:
            if self.grpc_service.message_q.qsize() > 0:
                lock.acquire()
                msg_params_string = self.grpc_service.message_q.get()
                msg_params = Message()
                msg_params.init_from_json_string(msg_params_string)
                msg_type = msg_params.get_type()
                for observer in self._observers:
                    observer.receive_message(msg_type, msg_params)
                lock.release()
        return

    def stop_receive_message(self):
        self.grpc_server.stop(None)
        self.is_running = False

    def notify(self, message: Message):
        msg_type = message.get_type()
        for observer in self._observers:
            observer.receive_message(msg_type, message)
