from fedml.fedml_core.distributed.communication.gRPC import grpc_comm_manager_pb2, grpc_comm_manager_pb2_grpc
import queue
import threading
import logging

from fedml.fedml_api.distributed.fedavg_gRPC.message_define import MyMessage
from fedml.fedml_core.distributed.communication.message import Message

lock = threading.Lock()


class gRPCCOMMServicer(grpc_comm_manager_pb2_grpc.gRPCCommManagerServicer):
    def __init__(self, host, port, client_num, client_id):
        self.host = host
        self.port = port
        self.client_num = client_num
        self.client_id = client_id

        if self.client_id == 0:
            self.node_type = "server"
        else:
            self.node_type = "client"

        self.message_q = queue.Queue(0)

    def sendMessage(self, request_iterator, context):
        # actually this rcp function is running at the server
        # it is used to treat the received message.
        context_ip = context.peer().split(":")[1]
        # logging.info("client_{} got msg from client_{} from ip address {}".format(
        #     self.client_id,
        #     request.server_id,
        #     context_ip
        # ))

        msg_params = Message()
        global_model_params = {}
        for i, request in enumerate(request_iterator):
            if i == 0:
                logging.info("client_{} got msg from client_{} from ip address {}".format(
                    self.client_id,
                    request.server_id,
                    context_ip
                ))
            k = request.fragment_id
            msg_params.init_from_json_string(request.message)
            payload = msg_params.get(MyMessage.MSG_ARG_KEY_MODEL_PARAMS)
            global_model_params[k] = payload

        msg_params.add(MyMessage.MSG_ARG_KEY_MODEL_PARAMS, global_model_params)

        lock.acquire()
        self.message_q.put(msg_params)
        lock.release()

        response = grpc_comm_manager_pb2.CommResponse()
        response.message = "message received"
        return response




