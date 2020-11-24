import simpy as sp
from random import Random, seed
from math import log
import process_classes as pc
import sys


SIM_TIME = 10000
ARRIVAL_RATE = 10
SEED = None


def expovariate(rate, stream):
    """generates a random number according to the exponential distribution given 'rate'"""
    u = stream.uniform(0, 1)
    return -log(u)/rate


def arrivals(env, dock, tracker):
    """event generator for train arrivals"""
    # generate separate random streams
    arrival_stream = Random()
    unload_stream = Random()
    crew_time_stream = Random()
    crew_arrival_stream = Random()

    latest_train = None  # used only at the end to wait on the final train departure
    while env.now <= SIM_TIME:
        yield env.timeout(expovariate(1/ARRIVAL_RATE, arrival_stream))  # wait amount of time according to exponential dist
        latest_train = pc.Train(env, unload_time=unload_stream.uniform(3.5, 4.5), dock=dock,
                                crew_time=crew_time_stream.uniform(6, 11), rand_stream=crew_arrival_stream, stats=tracker)

    yield latest_train.departed  # wait for final train departure (and end simulation when it departs)


def scheduled_arrivals(env, dock, tracker, schedule, travel_times):
    """event generator for pre-generated, scheduled arrivals"""
    latest_train = None  # used only at the end to wait on the final train departure
    for line in schedule:
        arrival, unload, crew_hours = line.strip().split()  # fetch pre-generated floats from file
        yield env.timeout(float(arrival) - env.now)  # wait until the next train arrival
        latest_train = pc.Train(env, unload_time=float(unload), dock=dock, crew_time=float(crew_hours),
                                stats=tracker, rand_stream=None, trav_times=travel_times)

    yield latest_train.departed  # wait for final train departure (and end simulation when it departs)


if __name__ == "__main__":
    env = sp.Environment()
    stats = pc.StatTracker(env)
    dock = sp.Resource(env, capacity=1)  # loading dock is a shared resource that creates an implied train queue

    args = sys.argv[1:]
    #args = ["-s", "schedule.txt", "traveltimes.txt"]  # used for testing/debugging
    #args = [ARRIVAL_RATE, SIM_TIME]  # used for testing/debugging
    if args[0] == "-s":
        arrival_schedule = open(args[1], 'r')
        new_crew_times = open(args[2], 'r')
        arrival_process = env.process(scheduled_arrivals(env, dock, stats, arrival_schedule, new_crew_times))

        env.run(arrival_process)  # ends sim when arrival_process ends (which is when the final train departs)

        arrival_schedule.close()
        new_crew_times.close()

    else:
        seed(SEED)  # used for debugging
        ARRIVAL_RATE = float(args[0])
        SIM_TIME = int(args[1])
        arrival_process = env.process(arrivals(env, dock, stats))  # creates arrival process/generator

        env.run(arrival_process)  # ends sim when arrival_process ends (which is when the final train departs)

    print(f"Time {env.now:.2f}: Simulation ended")
    stats.printout()  # print stats
