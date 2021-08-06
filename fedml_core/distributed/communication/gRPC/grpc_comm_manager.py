import logging

from typing import List
from concurrent import futures
import threading

import sys
import time
import json
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
from fedml.fedml_api.distributed.fedavg_gRPC.message_define import MyMessage


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

        self.service_default_config = {
            "retryPolicy": {
                "maxAttempts": 5,
                "initialBackoff": "0.15s",
                "maxBackoff": "1s",
                "backoffMultiplier": 2,
                "retryableStatusCodes": ["UNAVAILABLE"]
            }
        }
        self.service_default_config = json.dumps(self.service_default_config)
        self.opts = [('grpc.max_send_message_length', 1024 * 1024 * 1024),
                     ('grpc.max_receive_message_length', 1024 * 1024 * 1024),
                     ('grpc.enable_http_proxy', 0)]
                     #('grpc.keepalive_time_ms', 5000),
                     # send keepalive ping every 500 second, default is 2 hours
                     #('grpc.keepalive_timeout_ms', 50000),
                     # keepalive ping time out after 50 seconds, default is 20 seconds
                     #('grpc.keepalive_permit_without_calls', True),
                     # allow keepalive pings when there's no gPRC calls
                     #('grpc.http2.max_pings_without_data', 0),
                     # allow unlimited amount of keepalive pings without data
                     #('grpc.http2.min_time_between_pings_ms', 1000),
                     # allow grpc pings from client every 10 seconds
                     #('grpc.http2.min_ping_interval_without_data_ms', 5000)
                     # allow grpc ping from client without data every 5 seconds
                     #]

        self.client_args = [('grpc.max_send_message_length', 1024 * 1024 * 1024),
                     ('grpc.max_receive_message_length', 1024 * 1024 * 1024),
                     ('grpc.enable_http_proxy', 0)]
                     # ('grpc.enable_retries', 1)]
                     # ('grpc.peer_rpc_retry_buffer_size', 102400)
                     # ('grpc.service_config', '{"retryPolicy": {"maxAttempts": 4, "initialBackoff": "0.15s", "maxBackoff": "1s", "backoffMultiplier": 2, "retryableStatusCodes": ["UNAVAILABLE"]}}')]

        if client_id == 0:
            self.node_type = "server"
            self.init_server_communication()
        else:
            self.node_type = "client"
            self.init_client_communication()

        self.ip_config = build_ip_table(ip_config_path)
        self.is_running = True
        # logging.info("Communication is started with port " + str(port))

    def init_server_communication(self):
        # collecting local parameters from clients
        # staring collecting services at the server
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.client_num*100),
                                       maximum_concurrent_rpcs=1000,
                                       options=self.opts)
        # logging.info(self.host +":" +self.port)
        self.grpc_service = gRPCCOMMServicer(self.host, self.port, self.client_num, self.client_id)
        grpc_comm_manager_pb2_grpc.add_gRPCCommManagerServicer_to_server(
            self.grpc_service,
            self.grpc_server
        )

        # starts a grpc_server on local machine using ip address $host
        self.grpc_server.add_insecure_port("{}:{}".format(self.host, self.port))
        self.grpc_server.start()
        # logging.info("server started. Listening on port " + str(self.port))

    def init_client_communication(self):
        # downloading global parameters from server
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=1),
                                       maximum_concurrent_rpcs=1000,
                                       options=self.opts)
        self.grpc_service = gRPCCOMMServicer(self.host, self.port, self.client_num, self.client_id)
        grpc_comm_manager_pb2_grpc.add_gRPCCommManagerServicer_to_server(
            self.grpc_service,
            self.grpc_server
        )

        # starts a grpc_server on local machine using ip address $host
        self.grpc_server.add_insecure_port("{}:{}".format(self.host, self.port))
        self.grpc_server.start()
        # logging.info("client " + str(self.host) + " is started. Listening on port " + str(self.port))

    def send_message(self, msg: Message):
        # zrf revised this send_message() function to make it send more message in one flow.
        receiver_id = msg.get(Message.MSG_ARG_KEY_RECEIVER)
        sender_id = msg.get(Message.MSG_ARG_KEY_SENDER)
        global_model_params = msg.get(MyMessage.MSG_ARG_KEY_MODEL_PARAMS)
        message_type = msg.get_type()

        # lookup ip of receiver from self.ip_config table
        receiver_ip = self.ip_config[str(receiver_id)]
        channel_url = '{}:{}'.format(receiver_ip, str(50000 + receiver_id))

        # logging.info(channel_url)
        channel = grpc.insecure_channel(channel_url, options=self.client_args)
        stub = grpc_comm_manager_pb2_grpc.gRPCCommManagerStub(channel)

        def create_and_send_stream_message():
            for k in global_model_params.keys():
                message = Message(message_type, sender_id, receiver_id)
                message.add_params(MyMessage.MSG_ARG_KEY_MODEL_PARAMS, global_model_params[k])
                if message_type == MyMessage.MSG_TYPE_S2C_INIT_CONFIG:
                    client_index = msg.get(MyMessage.MSG_ARG_KEY_CLIENT_INDEX)
                    message.add_params(MyMessage.MSG_ARG_KEY_CLIENT_INDEX, str(client_index))
                elif message_type == MyMessage.MSG_TYPE_S2C_SYNC_MODEL_TO_CLIENT:
                    client_index = msg.get(MyMessage.MSG_ARG_KEY_CLIENT_INDEX)
                    message.add_params(MyMessage.MSG_ARG_KEY_CLIENT_INDEX, str(client_index))
                elif message_type == MyMessage.MSG_TYPE_C2S_SEND_MODEL_TO_SERVER:
                    local_sample_num = msg.get(MyMessage.MSG_ARG_KEY_NUM_SAMPLES)
                    message.add_params(MyMessage.MSG_ARG_KEY_NUM_SAMPLES, local_sample_num)

                payload = message.to_json()

                request = grpc_comm_manager_pb2.CommRequest()
                request.server_id = self.client_id
                request.message = payload
                request.fragment_id = str(k)
                logging.info("Send Message to Client_{} Fragment_{} Size_{} Time_{}".format(
                    receiver_id,
                    k,
                    sys.getsizeof(request),
                    time.time()
                ))
                yield request

        response = stub.sendMessage(create_and_send_stream_message())
        channel.close()
        logging.info("Finish Messaging to Client_{} Time_{}".format(receiver_id, time.time()))

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
                # msg_params = Message()
                # msg_params.init_from_json_string(msg_params_string)
                # msg_params.init_from_retreated_message(msg_params_string)
                msg_type = msg_params_string.get_type()
                for observer in self._observers:
                    observer.receive_message(msg_type, msg_params_string)
                    logging.info("Handling and Training: Client_{} Time_{}".format(
                        int(msg_params_string.get(MyMessage.MSG_ARG_KEY_SENDER)),
                        time.time()))
                lock.release()
        return

    def stop_receive_message(self):
        self.grpc_server.stop(None)
        self.is_running = False

    def notify(self, message: Message):
        msg_type = message.get_type()
        for observer in self._observers:
            observer.receive_message(msg_type, message)
