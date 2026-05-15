# This is to demonstration of how you can use the dsahboard.py as a stand-alone
# application and how to connect the vehical state to the dashboard.

from dashboard import TriggerAction
import keyboard

trigger_action = TriggerAction()  # creating dashboard trigger

# the below five method should be called before calling launch_dashboard() method to take effect
# note: this below five are optional
trigger_action.set_dashboard_size(1366, 768)  # aspect ratio 16:9
trigger_action.set_speedometer_range(240)

# to show dashboard note: this should be called at end of our code
trigger_action.launch_dashboard()

print("finished")
