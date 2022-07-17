# -*- coding: utf-8 -*-
# Created by: Raf
# Modify by: Vincentzyx

# import GameHelper as gh
# from GameHelper import GameHelper
import json
import os
import sys
import time
import threading
# import pyautogui
# import win32gui
# from PIL import Image
# import multiprocessing as mp
# import cv2
# import numpy as np

# from PyQt5 import QtGui, QtWidgets, QtCore
# from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPixmapItem, QInputDialog, QMessageBox
# from PyQt5.QtGui import QPixmap, QIcon
# from PyQt5.QtCore import QTime, QEventLoop
# from MainWindow import Ui_Form

from douzero.env.game import GameEnv
from douzero.evaluation.deep_agent import DeepAgent
import traceback

import BidModel
import LandlordModel
import FarmerModel
import jack_talk_ipc

EnvCard2RealCard = {3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
                    8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q',
                    13: 'K', 14: 'A', 17: '2', 20: 'JOKER_SMALL', 30: 'JOKER_BIG'}

RealCard2EnvCard = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
                    '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12,
                    'K': 13, 'A': 14, '2': 17, 'JOKER_SMALL': 20, 'JOKER_BIG': 30}

AllEnvCard = [3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7,
              8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12,
              12, 12, 12, 13, 13, 13, 13, 14, 14, 14, 14, 17, 17, 17, 17, 20, 30]

InitPlayerCardCount = 17

class hlddz_logger:

    def __init__(self):
        return
    
    @staticmethod
    def logger(log_content):
        print(log_content)
    
class hlddz_card_helper:

    def __init__(self):
        return

    @staticmethod
    def convert_game_card_to_douzero_card(game_card):
        return [RealCard2EnvCard[c] for c in list(game_card)]

    @staticmethod
    def convert_douzero_card_to_game_card(douzero_card):
        return [EnvCard2RealCard[c] for c in list(douzero_card)]



# helper = GameHelper()
# helper.ScreenZoomRate = 1.25  # 请修改屏幕缩放比

RPC_FUNCTION_CREATE_GAME_SESSION = "rpc_function_create_game_session"
RPC_FUNCTION_GAME_STATUS_TYPE_STARTED = "rpc_function_game_status_type_started"
RPC_FUNCTION_GAME_STATUS_TYPE_BIDDING = "rpc_function_game_status_type_bidding"
RPC_FUNCTION_GAME_STATUS_TYPE_ROBBING = "rpc_function_game_status_type_robbing"
RPC_FUNCTION_GAME_STATUS_TYPE_BIDDEN = "rpc_function_game_status_type_bidden"
RPC_FUNCTION_GAME_STATUS_TYPE_NO_ONE_BIDDING = "rpc_function_game_status_type_no_one_bidding"
RPC_FUNCTION_GAME_STATUS_TYPE_MULTIUPING = "rpc_function_game_status_type_multiuping"
RPC_FUNCTION_GAME_STATUS_TYPE_GIVING = "rpc_function_game_status_type_giving"
RPC_FUNCTION_GAME_STATUS_TYPE_GIVEN = "rpc_function_game_status_type_given"
RPC_FUNCTION_GAME_STATUS_TYPE_OVER = "rpc_function_game_status_type_over"

RPC_FUNCTION_ERROR_MESSAGE = """{"error":"no respond"}"""

RPC_MESSAGE_TOKEN_SSID = "ssid"
RPC_MESSAGE_TOKEN_FUNCTION = "function"
RPC_MESSAGE_TOKEN_PARAMETERS = "parameters"
RPC_MESSAGE_TOKEN_RETURN_LIST = "return_list"

class hlddz_bid:

    def __init__(self):
        return

    __BidThreshold1 = 65 # 叫地主阈值
    __BidThreshold2 = 72  # 抢地主阈值
    __JiabeiThreshold = (
        (85, 72),  # 叫地主 超级加倍 加倍 阈值
        (85, 75)   # 叫地主 超级加倍 加倍 阈值  (在地主是抢来的情况下)
    )
    __MingpaiThreshold = 92
    __my_self_hand_card = []
    __win_rate = 0

    def set_myself_handcards(self, hand_card_list):
        if int(hand_card_list[0]) != InitPlayerCardCount:
            hlddz_logger.logger("[error]card count is not 17")
            return
        self.__my_self_hand_card = hand_card_list[1:]
        self.__win_rate = BidModel.predict(self.__my_self_hand_card)

    def is_bid(self):
        if self.__win_rate > self.__BidThreshold1:
            return True
        else:
            return False

    def is_rob(self):
        if self.__win_rate > self.__BidThreshold2:
            return True
        else:
            return False   

class hlddz_ai_service:

    def __init__(self):
        self.game_reset()
        self.card_play_model_path_dict = {
            'landlord': "baselines/douzero_ADP/landlord.ckpt",
            'landlord_up': "baselines/douzero_ADP/landlord_up.ckpt",
            'landlord_down': "baselines/douzero_ADP/landlord_down.ckpt"
        }
        return

    __myself_view_chair_pos_constant = 0

    def game_reset(self):
        self.__landlord_view_chair_pos_idx = 0
        self.__my_view_chair_pos = ""
        self.__ai_players = [0, 0]
        self.__card_play_data_list = {}
        self.__user_hand_cards_env = []
        self.__three_landlord_cards_env = []
        self.__role_pos_table = ["","",""]
        self.__role_pos_farmer_table = ["","",""]

    def set_landlord_view_pos(self, view_chair_pos, bottom_card_list):
        self.__landlord_view_chair_pos_idx = int(view_chair_pos)
        self.__three_landlord_cards_env = hlddz_card_helper.convert_game_card_to_douzero_card(bottom_card_list)
        if  self.__landlord_view_chair_pos_idx == self.__myself_view_chair_pos_constant:
            self.__user_hand_cards_env += self.__three_landlord_cards_env
            self.__user_hand_cards_env.sort()
        self.__role_pos_table[self.__landlord_view_chair_pos_idx] = 'landlord'
        self.__role_pos_table[(self.__landlord_view_chair_pos_idx + 1) % 3] = 'landlord_down'
        self.__role_pos_table[(self.__landlord_view_chair_pos_idx + 2) % 3] = 'landlord_up'

        self.__role_pos_farmer_table[self.__landlord_view_chair_pos_idx] = 'landlord'
        self.__role_pos_farmer_table[(self.__landlord_view_chair_pos_idx + 1) % 3] = 'down'
        self.__role_pos_farmer_table[(self.__landlord_view_chair_pos_idx + 2) % 3] = 'up'        

        # self.__my_view_chair_pos = self.__role_pos_table[self.__myself_view_chair_pos_constant]
        # if self.__landlord_view_chair_pos_idx == 0:
        #     self.__my_view_chair_pos = "landlord"
        # elif self.__landlord_view_chair_pos_idx == 1:
        #     self.__my_view_chair_pos = "landlord_up"
        # elif self.__landlord_view_chair_pos_idx == 2:
        #     self.__my_view_chair_pos = "landlord_down"

        # 创建一个代表玩家的AI
        self.__ai_players[0] = self.__role_pos_table[self.__myself_view_chair_pos_constant]
        self.__ai_players[1] = DeepAgent(self.__role_pos_table[self.__myself_view_chair_pos_constant], self.card_play_model_path_dict[self.__role_pos_table[self.__myself_view_chair_pos_constant]])
        self.__env = GameEnv(self.__ai_players) 
        self.__env.reset()
        self.__env.game_over = False

        # 整副牌减去玩家手上的牌，就是其他人的手牌,再分配给另外两个角色（如何分配对AI判断没有影响）
        other_hand_cards = []
        for i in set(AllEnvCard):
            other_hand_cards.extend([i] * (AllEnvCard.count(i) - self.__user_hand_cards_env.count(i)))
        self.__card_play_data_list.update({
            'three_landlord_cards': self.__three_landlord_cards_env,
            self.__role_pos_table[(self.__myself_view_chair_pos_constant + 0) % 3]:self.__user_hand_cards_env,
            self.__role_pos_table[(self.__myself_view_chair_pos_constant + 1) % 3]:
                other_hand_cards[0:17] if (self.__myself_view_chair_pos_constant + 1) % 3 != self.__landlord_view_chair_pos_idx else other_hand_cards[17:],
            self.__role_pos_table[(self.__myself_view_chair_pos_constant + 2) % 3]:
                other_hand_cards[0:17] if (self.__myself_view_chair_pos_constant + 1) % 3 == self.__landlord_view_chair_pos_idx else other_hand_cards[17:]
        })
        self.__env.card_play_init(self.__card_play_data_list)


    def set_myself_handcards(self, hand_card_list):
        if int(hand_card_list[0]) != InitPlayerCardCount:
            hlddz_logger.logger("[error]card count is not 17")
            return
        self.__user_hand_cards_env = hlddz_card_helper.convert_game_card_to_douzero_card(hand_card_list[1:])
        return

    def is_multiup(self):
        win_rate = 0
        if self.__landlord_view_chair_pos_idx == self.__myself_view_chair_pos_constant:
            win_rate = LandlordModel.predict(hlddz_card_helper.convert_douzero_card_to_game_card(self.__user_hand_cards_env))
        else:
            user_position = self.__role_pos_farmer_table[self.__myself_view_chair_pos_constant]
            win_rate = FarmerModel.predict(hlddz_card_helper.convert_douzero_card_to_game_card(self.__user_hand_cards_env),
             hlddz_card_helper.convert_douzero_card_to_game_card(self.__three_landlord_cards_env), user_position) - 5
        if win_rate > 72:
            return True
        return False

    def giving_cards(self):
        giving_cards = []
        action_message = self.__env.step(self.__role_pos_table[self.__myself_view_chair_pos_constant])
        print(action_message)
        giving_cards = action_message["action"]
        print("myself current left:" + str(self.__env.game_infoset.num_cards_left_dict[self.__role_pos_table[self.__myself_view_chair_pos_constant]]))
        return giving_cards

    def given_cards(self, view_chair_pos, given_card_list):
        if view_chair_pos == self.__myself_view_chair_pos_constant:
            return
        given_card_len = int(given_card_list[0])
        other_played_cards_env = []
        user_position = self.__role_pos_table[self.__myself_view_chair_pos_constant]
        # user_position = self.__role_pos_table[view_chair_pos]
        if given_card_len != 0:
            other_played_cards_env = hlddz_card_helper.convert_game_card_to_douzero_card(given_card_list[1:])
            other_played_cards_env.sort()
        self.__env.step(user_position, other_played_cards_env)

        given_user_position = self.__role_pos_table[view_chair_pos]
        print("current left:" + str(self.__env.game_infoset.num_cards_left_dict[given_user_position]))
        return

    def current_game_over(self):
        self.__env.game_over = True
        return

class hlddz_business:

    def __init__(self):
        self.__hlddz_bid = hlddz_bid()
        self.__hlddz_ai_service = hlddz_ai_service()
        return

    def get_create_game_session_message(self):
        ssid = self.get_game_ssid()
        return_list = []
        return_list.append(ssid)
        ret_msg = self.make_respond_message(ssid, RPC_FUNCTION_CREATE_GAME_SESSION, return_list)
        return ret_msg

    def get_default_ok_respond_message(self, cur_ssid, function_name):
        ssid = cur_ssid
        return_list = ["1"]
        ret_msg = self.make_respond_message(ssid, function_name, return_list)
        return ret_msg

    def get_is_bid_respond_message(self, cur_ssid, function_name):
        ssid = cur_ssid
        res = self.__hlddz_bid.is_bid()
        return_list = []
        if res == True:
            return_list = ["1"]
        else:
            return_list = ["0"]
        ret_msg = self.make_respond_message(ssid, function_name, return_list)
        return ret_msg

    def get_is_robbed_respond_message(self, cur_ssid, function_name):
        ssid = cur_ssid
        res = self.__hlddz_bid.is_rob()
        return_list = []
        if res == True:
            return_list = ["1"]
        else:
            return_list = ["0"]
        ret_msg = self.make_respond_message(ssid, function_name, return_list)
        return ret_msg

    def get_is_multied_respond_message(self, cur_ssid, function_name):
        ssid = cur_ssid
        res = self.__hlddz_ai_service.is_multiup()
        return_list = []
        if res == True:
            return_list = ["1"]
        else:
            return_list = ["0"]
        ret_msg = self.make_respond_message(ssid, function_name, return_list)
        return ret_msg

    def get_giving_card_respond_message(self, cur_ssid, function_name, giving_cards):
        ssid = cur_ssid
        return_list = giving_cards
        ret_msg = self.make_respond_message(ssid, function_name, return_list)
        return ret_msg        

    def get_respond_message(self, cur_request_message):
        respond_message = RPC_FUNCTION_ERROR_MESSAGE
        game_ssid, function_name, parameters = self.parse_request_message(cur_request_message)
        if function_name == RPC_FUNCTION_CREATE_GAME_SESSION:
            respond_message = self.get_create_game_session_message()
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_STARTED:
            self.__hlddz_bid.set_myself_handcards(parameters)
            self.__hlddz_ai_service.set_myself_handcards(parameters)
            respond_message = self.get_default_ok_respond_message(game_ssid, function_name)
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_BIDDING:
            respond_message = self.get_is_bid_respond_message(game_ssid, function_name)
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_ROBBING:
            respond_message = self.get_is_robbed_respond_message(game_ssid, function_name)            
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_BIDDEN:
            self.__hlddz_ai_service.set_landlord_view_pos(parameters[0], parameters[2:])
            respond_message = self.get_default_ok_respond_message(game_ssid, function_name)
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_MULTIUPING:
            respond_message = self.get_is_multied_respond_message(game_ssid, function_name)            
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_GIVING:
            giving_cards = self.__hlddz_ai_service.giving_cards()
            respond_message = self.get_giving_card_respond_message(game_ssid, function_name, giving_cards)
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_GIVEN:
            if len(parameters) >= 2:
                self.__hlddz_ai_service.given_cards(int(parameters[0]),parameters[1:])
            respond_message = self.get_default_ok_respond_message(game_ssid, function_name)            
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_OVER:
            self.__hlddz_ai_service.current_game_over()
            respond_message = self.get_default_ok_respond_message(game_ssid, function_name)
        elif function_name == RPC_FUNCTION_GAME_STATUS_TYPE_NO_ONE_BIDDING:
            self.__hlddz_ai_service.game_reset()
            respond_message = self.get_default_ok_respond_message(game_ssid, function_name)
        return respond_message
    
    def get_game_ssid(self):
        self.__game_ssid_counter = self.__game_ssid_counter + 1
        return str(self.__game_ssid_counter)

    def make_request_message(self,game_ssid, function_name, parameters):
        request_object = {}
        request_object[RPC_MESSAGE_TOKEN_SSID] = game_ssid
        request_object[RPC_MESSAGE_TOKEN_FUNCTION] = function_name
        request_object[RPC_MESSAGE_TOKEN_PARAMETERS] = parameters
        request_message = json.dumps(request_object)
        return request_message

    def make_respond_message(self,game_ssid, function_name, return_list):
        respond_object = {}
        respond_object[RPC_MESSAGE_TOKEN_SSID] = game_ssid
        respond_object[RPC_MESSAGE_TOKEN_FUNCTION] = function_name
        respond_object[RPC_MESSAGE_TOKEN_RETURN_LIST] = return_list
        respond_message = json.dumps(respond_object)
        return respond_message

    def parse_request_message(self, request_message):
        req_dict = json.loads(request_message)

        game_ssid = ""
        if RPC_MESSAGE_TOKEN_SSID in req_dict:
            game_ssid = req_dict[RPC_MESSAGE_TOKEN_SSID]

        function_name = ""
        if RPC_MESSAGE_TOKEN_FUNCTION in req_dict:
            function_name = req_dict[RPC_MESSAGE_TOKEN_FUNCTION]
        
        parameters = []
        if RPC_MESSAGE_TOKEN_PARAMETERS in req_dict:
            parameters = req_dict[RPC_MESSAGE_TOKEN_PARAMETERS]
        return game_ssid, function_name, parameters

    __game_ssid_counter = 0

if __name__ == '__main__':

    # hlddz_bid = hlddz_bid()
    # hlddz_bid.set_myself_handcards(["17","JOKER_BIG","JOKER_SMALL","2","2","A","K","J","10","9","9","8","7","7","6","5","4","3"])
    # ai_svc = hlddz_ai_service()
    # ai_svc.set_myself_handcards(["17","JOKER_BIG","JOKER_SMALL","2","2","A","K","J","10","9","9","8","7","7","6","5","4","3"])
    # ai_svc.set_landlord_view_pos(0, ["J","6","2"])
    # ai_svc.is_multiup()
    # my_giving_cards = ai_svc.giving_cards()
    # ai_svc.given_cards(1, ["5","9","8","7","6","5"])
    # ai_svc.given_cards(2, ["0"])
    # my_giving_cards = ai_svc.giving_cards()
    # ai_svc.given_cards(1, ["0"])
    # ai_svc.given_cards(2, ["5","J","10","9","8","7"])
    # my_giving_cards = ai_svc.giving_cards()

    business_object = hlddz_business()
    jack_talk_ipc.initialize_jack_talk_ipc_svc()
    jack_talk_ipc.start_jack_talk_ipc_svc()

    while True:
        recv_msg = jack_talk_ipc.recv_talk_message()
        respond_msg = business_object.get_respond_message(recv_msg)
        jack_talk_ipc.send_talk_message(respond_msg)
        
    jack_talk_ipc.stop_jack_talk_ipc_svc()
    jack_talk_ipc.deinitialize_jack_talk_ipc_svc()
