""" State and state machine Code """
import logging
from typing import List

logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format=f'[STATES] %(asctime)s - %(levelname)s - %(message)s')

class State():
    @staticmethod
    def determine_next_state(event: str) -> "State":
        pass
    
    @classmethod
    def process_event(cls, event: str) -> "State":
        """Process an event

        :param event: event to process
        :return: next state to move to, if any
        """
        logging.debug(f"State {cls.name()} processing event {event}")
        return cls.determine_next_state(event)
    
    @classmethod
    def name(cls):
        return cls.__name__
    
class StateMachine():    
    states: List[State]
    previous_state: State
    state: State
    
    def get_next_state(self, event: str) -> State:
        """Get the next state but do not move to it

        :param event: event to test
        :return: potential next state or current state
        """
        return self.state.process_event(event)
        
    def transition(self, event: str) -> State:
        """Handle a state transition

        :param event: event to handle
        :return: new state of machine
        """
        old_state = self.state
        new_state = self.get_next_state(event)
        
        if new_state != old_state:
            if new_state.name() == "PreviousState":
                self.state = self.previous_state
                self.previous_state = old_state
            else:
                self.previous_state = old_state
                self.state = new_state
            logging.info(f"Transitioned from {old_state.name()} to {self.state.name()}")
        else:
            logging.debug(f"No transition from {old_state.name()} for event {event}")
            
        return self.state
    
    def __str__(self):
        return self.__class__.__name__
    
class ControllerStates:
    
    class PreviousState(State):
        """Placeholder state to notify state machine to revert to previous state
        """
        pass
    
    class PathBlockedState(State):
        def determine_next_state(event):
            match event:
                case "path_unblocked":
                    return ControllerStates.PreviousState
                case "path_blocked":
                    return ControllerStates.PathBlockedState
                case _:
                    return ControllerStates.PathBlockedState
    
    class MovingToAisleState(State):
        def determine_next_state(event):
            match event:
                case "picking_init":
                    return ControllerStates.PickingState
                case "path_blocked":
                    return ControllerStates.PathBlockedState
                case _:
                    return ControllerStates.MovingToAisleState 

    class ExitAisleState(State):
        def determine_next_state(event):
            match event:
                case "to_aisle":
                    return ControllerStates.MovingToAisleState
                case "to_hub":
                    return ControllerStates.MovingToHubState
                case "path_blocked":
                    return ControllerStates.PathBlockedState
                case _:
                    return ControllerStates.ExitAisleState
                
    class MovingToHubState(State):
        def determine_next_state(event):
            match event:
                case "movement_complete":
                    return ControllerStates.IdleState
                case "path_blocked":
                    return ControllerStates.PathBlockedState
                case _:
                    return ControllerStates.MovingToHubState 
                
    class PickingState(State):
        def determine_next_state(event):
            match event:
                case "order_complete":
                    return ControllerStates.MovingToHubState
                case "aisle_complete":
                    return ControllerStates.MovingToAisleState
                case "path_blocked":
                    return ControllerStates.PathBlockedState
                case "color_detected":
                    return ControllerStates.GrabbingState
                case "not_detected":
                    return ControllerStates.ExitAisleState
                case _:
                    return ControllerStates.PickingState 
                
    class GrabbingState(State):
        def determine_next_state(event):
            match event:
                case "order_grabbed":
                    return ControllerStates.PickingState
                case "exiting":
                    return ControllerStates.ExitAisleState
                case _:
                    return ControllerStates.GrabbingState 
        
    class IdleState(State):
        def determine_next_state(event):
            match event:
                case "order_received":
                    return ControllerStates.MovingToAisleState
                case _:
                    return ControllerStates.IdleState
                    
    class InitState(State):
        def determine_next_state(event):
            match event:
                case "init_done":
                    return ControllerStates.IdleState
                case _:
                    return ControllerStates.InitState
    
    def __new__(cls):
        return [
            cls.InitState,
            cls.IdleState,
            cls.PickingState
        ]
    
class ControllerStateMachine(StateMachine):      
    instance = None
    _initialized = False  
    def __new__(cls): 
        if cls.instance == None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not self._initialized:
            self.previous_state = None
            self.state = ControllerStates.InitState