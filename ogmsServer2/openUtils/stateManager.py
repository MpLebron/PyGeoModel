"""
Author: DiChen
Date: 2024-09-06 17:21:20
LastEditors: DiChen
LastEditTime: 2024-09-13 21:54:57
"""

"""
Author: DiChen
Date: 2024-09-06 17:21:20
LastEditors: DiChen
LastEditTime: 2024-09-08 16:23:59
"""

# 定义状态常量
STATE_INIT = 0b1  # 1: init
STATE_RUNNING = 0b10  # 2: running
STATE_COMPLETED = 0b100  # 4: completed
STATE_ERROR = 0b1000  # 8: error


class StateManager:
    def __init__(self):
        # init state
        self.state = STATE_INIT
        print(f"StateManager initialized in state: {bin(self.state)}")

    def addState(self, state):
        """add state"""
        self.state |= state

    def removeState(self, state):
        """remove state"""
        self.state &= ~state

    def hasStatus(self, state):
        """check state"""
        return self.state & state != 0

    def trans2Status(self, state):
        """transition to state"""
        if state == STATE_RUNNING and not self.hasStatus(STATE_INIT):
            print("Cannot run without initialization")
            return

        if state == STATE_COMPLETED and not self.hasStatus(STATE_RUNNING):
            print("Cannot complete without running")
            return

        if state == STATE_ERROR:
            print("Error occurred, transitioning to ERROR state")
            self.state = state
            return

        self.state = state
        print(f"Transitioned to state: {bin(self.state)}")

    def getState(self):
        """get state"""
        return bin(self.state)

    def checkInputStatus(self, status):
        """check input status"""
        if status == 1 and self.state == STATE_INIT:
            self.addState(STATE_RUNNING)
            print("model service calculating!")
        elif status == 2:
            self.addState(STATE_COMPLETED)
            print("model calculation was completed!")
