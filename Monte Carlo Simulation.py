#!/usr/bin/python
import math
import matplotlib.pyplot as plt
import numpy as np

print("Welcome to the Monte Carlo Simulation and Output Analysis.(Developed By Peter Azmy)\n\n")
x0,y0 = input("Please input the Troop Starting levels (x0 y0): ").split()
print("\nx0 Value: ", x0)
print("\ny0 Value: ", y0)
print("\nGreat! Now please input the following Lethality Coefficients (α and β): ")
a,b = input("Please input the Troop Starting levels (α β): ").split()
print("\nα (Aplha) Value: ", a)
print("\nβ (Beta) Value: ", b)
print("\nHow many steps?\n")
steptime = int(input("Steps: "))
enforcer_timesa = int (input("How many times will reinforcements arrive? (enter a number between 0-3)\n"))
if enforcer_timesa > 3 or enforcer_timesa < 0:
  enforcer_timesa = input("Invalid response. Please enter a number valid response: ")

enforcer_timesb = int (input("How many times will reinforcements arrive? (enter a number between 0-3)\n"))
if enforcer_timesb > 3 or enforcer_timesb < 0:
  enforcer_timesb = input("Invalid response. Please enter a number between 0-3")

call_enforcersa = float (input("When will reinforcements arrive? (enter 0.1%-0.8%)\n"))
if call_enforcersa < 0.1 or call_enforcersa > 0.9:
  call_enforcersa = input("Invalid response. Please enter a number valid response: ")

call_enforcersb = float (input("When will reinforcements arrive? (enter 0.1%-0.8%)\n"))
if call_enforcersb < 0.1 or call_enforcersb > 0.9:
  call_enforcersb = input("Invalid response. Please enter a number valid response: ")


enforcer_amounta = float(input("How many reinforcements will arrive? (Enter a number between 0.1-0.5%\n"))
if enforcer_amounta < 0.1 or enforcer_amounta > 0.5:
  enforcer_amounta = input("Invalid response. Please enter a number valid response: ")
  

enforcer_amountb = float(input("How many reinforcements will arrive? (Enter a number between 0.1-0.5%\n"))
if enforcer_amounta < 0.1 or enforcer_amounta > 0.5:
  enforcer_amounta = input("Invalid response. Please enter a number valid response: ")

alpha_enforcers = float (input("How strong are the new troops? (enter .3-.9)\n"))
if alpha_enforcers < 0.3 or alpha_enforcers > 0.9:
  alpha_enforcers = input("Invalid response. Please enter a number valid response: ")

beta_enforcers = float (input("How strong are the new troops? (enter .3-.9)\n"))
if beta_enforcers < 0.3 or beta_enforcers > 0.9:
  beta_enforcers = input("Invalid response. Please enter a number valid response: ")

deltaT= int(1/steptime)
XTroops = []
YTroops = []
XTroops.append(x0)
YTroops.append(y0)
XTroops_init = XTroops
YTroops_init = YTroops
A = float(a)
B = float(b)
for f in range(steptime):
    if(int(XTroops[f]) > 0 and int(YTroops[f]) > 0):
        dxdt = float(YTroops[f])*B
        dydt = float(XTroops[f])*A
        print(dxdt, dydt)
        if dxdt > 0.0 and dydt > 0.0 and int(XTroops[f]) > 0 and int(YTroops[f])> 0:
            YTroops.append(float(YTroops[f])-dydt*deltaT)
            XTroops.append(float(XTroops[f])-dxdt*deltaT)
            print(XTroops[f],YTroops[f])
            print('\n')
        else:
            print("loop never happened")
            break
if (XTroops < XTroops_init*call_enforcersa and enforcer_timesa > 0): 
    reinforcement = XTroops_init * enforcer_amounta
    new_alpha = ((XTroops_init * A) + (alpha_enforcers * reinforcement)/(XTroops_init + reinforcement))
    XTroops = XTroops + reinforcement
    call_enforcersa = call_enforcersa - 1

if(YTroops < YTroops_init*call_enforcersb and enforcer_timesb > 0): 
    reinforcementb = YTroops_init * enforcer_amountb 
    new_beta = ((YTroops_init * B) + (beta_enforcers * reinforcementb)/(YTroops_init + reinforcementb))
    YTroops = YTroops + reinforcementb 
    call_enforcersb = call_enforcersb - 1

plt.plot(XTroops, 'r-',label="Troop 1")
plt.plot(YTroops, 'b',label="Troop 2")
plt.xlabel('Steps') 
plt.ylabel('Survivors')  
plt.title('Results')
plt.show()

#temp(f+1) = f - int(-1*B*Y0)
#temp2(f+1) = f - int(-1*A*X0)
  


  
