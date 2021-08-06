import time

from fedml.fedml_core.distributed.communication.gRPC import grpc_comm_manager_pb2, grpc_comm_manager_pb2_grpc
import queue
import threading
import logging
import grpc
import time

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
        try:
            context_ip = context.peer().split(":")[1]

            msg_params = Message()
            global_model_params = {}
            for request in request_iterator:
                logging.info("Receive Message: Client_{} From Client_{} Fragment_{} Time_{}".format(
                    self.client_id,
                    request.server_id,
                    context_ip,
                    request.fragment_id,
                    time.time()
                ))
                k = request.fragment_id
                msg_params.init_from_json_string(request.message)
                payload = msg_params.get(MyMessage.MSG_ARG_KEY_MODEL_PARAMS)
                global_model_params[k] = payload

            msg_params.add(MyMessage.MSG_ARG_KEY_MODEL_PARAMS, global_model_params)
            logging.info("Finish Receiving Msg: Client_{} from Client_{}".format(
                self.client_id,
                msg_params.get(MyMessage.MSG_ARG_KEY_SENDER)
            ))

            lock.acquire()
            self.message_q.put(msg_params)
            lock.release()

            response = grpc_comm_manager_pb2.CommResponse()
            response.client_id = self.client_id
        except grpc.RpcError as e:
            logging.info("Throw Errors when Receiving Msg! Code:{}; Details{}".format(
                e.code(), e.details()
            ))
        return response




