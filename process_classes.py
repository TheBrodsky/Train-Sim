import simpy as sp
from random import Random
from itertools import count
from collections import defaultdict

class Train:
    num_trains = count(0)

    def __init__(self, env, unload_time, dock, crew_time, stats, rand_stream, trav_times=None):
        self.env = env
        self.arrival = env.now  # used for time-in-system stat
        self.tracker = stats  # stat tracker
        self.id = next(self.num_trains)
        self.unload_time = unload_time
        self.time_entered_dock = 0  # used for tracking progress of unload when train hogs out during service
        self.crew = Crew(self.env, crew_time, self)  # create the corresponding crew process
        self.action = env.process(self.run(dock))  # the train process; used by crew to interrupt upon hogout
        self.num_hogouts = 0  # used for stats
        self.rand_stream = rand_stream  # random stream for crew arrival times
        self.travel_times = trav_times  # gives train access to pregenerated file of crew arrival times
        self.departed = env.event()  # used in conditional event to kill crew processes when train terminates


    def run(self, dock):
        '''The train process. Consists of two parts: 1) waiting in queue, 2) waiting to unload'''
        print(f"Time {self.env.now:.2f}: train {self.id} arrival for {self.unload_time:.2f}h of unloading,",
              f"crew {self.crew.id} with {self.crew.remaining_time:.2f}h before hogout (Q={len(dock.queue)})")
        self.env.process(self.crew.run())  # run the previously created crew process
        req = dock.request()  # creates a request for the dock; adds train to queue

        while True:
            # this loop runs while the train waits to enter dock
            try:
                self.tracker.update_queue(len(dock.queue))  # tell tracker that queue has updated
                yield req
                print(f"Time {self.env.now:.2f}: train {self.id} entering dock for {self.unload_time:.2f}h of unloading,",
                      f"crew {self.crew.id} with {self.crew_remaining_time():.2f}h before hogout")
                self.tracker.update_queue(len(dock.queue))  # tell tracker that queue has updated
                self.tracker.update_dock(1)  # tell stat tracker that dock is now busy
                self.time_entered_dock = self.env.now
                break
            except sp.Interrupt:
                # hogout in queue
                self.num_hogouts += 1
                print(f"Time {self.env.now:.2f}: train {self.id} crew {self.crew.id} hogged out in queue (SERVER HOGGED)")
                self.crew = self.new_crew()  # create new crew process
                self.env.process(self.crew.run())  # run new crew process

                if self.travel_times is not None:
                    # pre-generated travel time
                    yield self.env.timeout(float(self.travel_times.readline().strip()))
                else:
                    # random travel time
                    yield self.env.timeout(self.rand_stream.uniform(2.5, 3.5))  # wait for new crew to arrive

                print(f"Time {self.env.now:.2f}: train {self.id} replacement crew {self.crew.id} arrives (SERVER UNHOGGED)")
                continue

        while True:
            # this loop runs while the train waits to be unloaded
            try:
                yield self.env.timeout(self.unload_time)  # wait for unload
                print(f"Time {self.env.now:.2f}: train {self.id} departing (Q={len(dock.queue)})")
                self.tracker.update_dock(0)  # tell stat tracker that dock is now idle
                self.tracker.scrape_train_info(self)  # gathers relevant train stats before process terminates
                self.departed.succeed()  # ends corresponding crew process; ends simulation if last train
                dock.release(req)
                break
            except sp.Interrupt:
                # hogout during unload
                self.num_hogouts += 1
                self.unload_time -= self.env.now - self.time_entered_dock  # update unload time for partial unload
                print(f"Time {self.env.now:.2f}: train {self.id} crew {self.crew.id} hogged out during service (SERVER HOGGED)")
                self.tracker.update_dock(-1)  # tell stat tracker that dock is now hogged out
                self.crew = self.new_crew()  # create new crew process
                self.env.process(self.crew.run())  # run new crew process

                if self.travel_times is not None:
                    # pre-generated travel time
                    yield self.env.timeout(float(self.travel_times.readline().strip()))
                else:
                    # random travel time
                    yield self.env.timeout(self.rand_stream.uniform(2.5, 3.5))  # wait for new crew to arrive

                self.tracker.update_dock(1)  # tell stat tracker that dock is busy again
                print(f"Time {self.env.now:.2f}: train {self.id} replacement crew {self.crew.id} arrives (SERVER UNHOGGED)")
                continue


    def new_crew(self):
        '''creates replacement crew'''
        return Crew(self.env, 12, self)

    def crew_remaining_time(self):
        '''this is needed because the crew's remaining time doesn't count down, it just waits until it expires'''
        return self.crew.remaining_time - (self.env.now - self.crew.arrival)


class Crew:
    num_crews = count(0)

    def __init__(self, env, time, train):
        self.env = env
        self.arrival = self.env.now
        self.id = next(self.num_crews)
        self.remaining_time = time
        self.train = train


    def run(self):
        '''crew process; waits until hogout and interrupts train process'''
        yield self.env.timeout(self.remaining_time) | self.train.departed
        if not self.train.departed.processed:  # crew process ends if train departs
            self.train.action.interrupt()


class StatTracker:
    """Used to track the simulation statistics and print them out"""

    def __init__(self, env):
        self.env = env
        self.time_in_system = []  # list of how much time each train spent in system
        self.prior_dock_update = 0  # keeps track of last time "update_dock" was called
        self.dock_status = 0  # 0 = idle, 1 = busy, -1 = hogged out and idle
        self.status_times = [0, 0, 0]  # tracks amount of time spent in each dock status
        self.queue_time_integral = 0  # used for time average of trains in queue
        self.prior_queue_update = 0  # keeps track of last time "update_queue" was called
        self.queue_len = 0  # previously recorded queue length
        self.max_queue = 0  # largest recorded queue length
        self.hogouts = defaultdict(int)  # dictionary of hogout counts

    def printout(self):
        """Prints out the post-simulation statistics"""
        print("\nStatistics")
        print(f"Total number of trains served: {next(Train.num_trains)}")
        print(f"Average time-in-system per train: {sum(self.time_in_system) / len(self.time_in_system):.2f}h")
        print(f"Maximum time-in-system per train: {max(self.time_in_system):.2f}h")
        print(f"Dock idle percentage: {((self.status_times[0] + self.status_times[-1]) / self.env.now) * 100:.2f}%")
        print(f"Dock busy percentage: {(self.status_times[1] / self.env.now) * 100:.2f}%")
        print(f"Dock hogged-out percentage: {(self.status_times[-1] / self.env.now) * 100:.2f}%")
        print(f"Time average number of trains in queue: {self.queue_time_integral / self.env.now:.3f}")
        print(f"Maximum number of trains in queue: {self.max_queue}")
        print("Histogram of hogout count per train:")
        self.print_histogram()


    def scrape_train_info(self, train):
        """Gathers information that can only be gathered when a train is departing"""
        self.time_in_system.append(self.env.now - train.arrival)
        self.hogouts[train.num_hogouts] += 1


    def update_dock(self, status):
        """Used to compute dock percentages"""
        self.status_times[self.dock_status] += self.env.now - self.prior_dock_update  # record length of time after . . .
            # . . . last call to this function but before the dock status is changed

        self.dock_status = status  # new status
        self.prior_dock_update = self.env.now  # new time


    def update_queue(self, queue_length):
        """Used to compute max trains in queue and time average of trains in queue"""
        self.max_queue = max(self.max_queue, queue_length)  # check for max queue length
        self.queue_time_integral += self.queue_len * (self.env.now - self.prior_queue_update)
        self.prior_queue_update = self.env.now  # new time
        self.queue_len = queue_length  # new queue length

    def print_histogram(self):
        for hogouts, count in sorted(self.hogouts.items()):
            print(f"[{hogouts}]: {count}")

    def get_time_in_system(self):  # used in batch running of simulation to compute confidence interval/mean
        return self.time_in_system

    def avg_hogouts(self):  # used as proxy to determine when the sim is "overloaded"
        """Returns the average number of hogouts per train in simulation"""
        sum = 0
        for hogouts, num_trains in self.hogouts.items():
            sum += hogouts * num_trains
        return sum/len(self.time_in_system)