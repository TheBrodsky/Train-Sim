from random import uniform, seed
import data_structures as ds
from math import log
import sys
#seed(100)


def expovariate(rate):
    '''generates a random number according to the exponential distribution'''
    u = uniform(0, 1)
    return -log(u)/rate


def generate_arrival_events(sim_time, arrival_average):
    '''generate every arrival event that will happen throughout the sim; returns priority queue'''
    '''MUST NOT BE USED WITH parse_train_arrival_file'''
    eventQueue = ds.eventQueue()
    now = 0
    current_train = 0  # for tracking train id

    while now < sim_time:
        interval = round(expovariate(1/arrival_average), 2)  # the poisson process
        now += interval
        if now >= sim_time:
            break
        else:
            eventQueue.push(ds.train(now, current_train))
            current_train += 1

    return eventQueue


def parse_train_arrival_file(file):
    '''generates every arrival event based on a provided arrival schedule; returns priority queue'''
    '''MUST NOT BE USED WITH generate_arrival_events'''
    eventQueue = ds.eventQueue()
    current_train = 0

    for line in file:
        arrival, unload, crew_hours = line.strip().split()
        train = ds.train(float(arrival), current_train)  # create train object with specified arrival time
        train.override_train_values(float(unload), float(crew_hours))  # override the random values for unload and crew
        eventQueue.push(train)
        current_train += 1

    return eventQueue


def parse_crew_arrival_file(file):
    '''returns a list containing all the pre-generated crew arrival times'''
    crew_times = []
    for line in file:
        crew_times.append(float(line.strip()))

    return crew_times


def get_args():
    return sys.argv[1:]

    #args = input()
    #args = args.strip().split()
    #return args

