#!/usr/bin/python
#import matplotlib.pyplot as plt
#import numpy as np
import statistics

print(
    "Welcome to the Queue-Server Simulation and Analysis Program! (Developed By Peter Azmy)\n\n"
)
ServerName, ServerCapacity, EntityName = input(
    "Please input the Server Name, Capacity, and Entity with which you are Modeling: "
).split()
print("\nServer Name:", ServerName)
print("\nServer Capacity:", ServerCapacity)
print("\nEntity Name:", EntityName)
lengthoftimes = int(
    input(
        "\n\nPlease enter number how many Inter-Arrival times are about to be inputted: "
    ))

arrivaltimes = list(map(
    int,
    input("\nEnter the numbers : ").strip().split()))[:lengthoftimes]

print("\nCurrent Respective Inter-Arrival Times: ", arrivaltimes)

servicetimes = list(
    map(
        int,
        input("\n\nEnter the respective numbers Service times: ").strip().
        split()))[:lengthoftimes]

print("\nCurrent Respective Service Times: ", arrivaltimes)


print ("\nQueue Method \nMaximum Queue Length = %3.1f" % max(arrivaltimes))
print ("Minimum Queue Length = %3.1f" % min(arrivaltimes))

print ("\nTotal Queue Time = %3.1f" % sum(lengthoftimes))

print ("\nMean Waiting Time = %3.1f" % statistics.mean(lengthoftimes))
print ("Variance of Waiting Time = %3.1f" % statistics.variance(lengthoftimes)) 
