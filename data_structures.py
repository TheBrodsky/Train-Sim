import heapq as hq
from collections import defaultdict
from random import uniform, seed
#seed(100)

class eventQueue:
    def __init__(self):
        self.container = []

    def push(self, element):
        '''adds an event to the back of the queue'''
        hq.heappush(self.container, element)

    def pop(self):
        '''returns the earliest event remaining in the queue'''
        item = hq.heappop(self.container)
        return item

    def is_empty(self):
        return len(self.container) == 0

    def peak_top(self):
        try:
            return self.container[0]
        except IndexError:
            return None

    def size(self):
        return len(self.container)


class trainQueue:
    def __init__(self):
        self.trains = []

    def enqueue(self, train):
        '''adds a train to the back of the queue'''
        hq.heappush(self.trains, train)

    def dequeue(self):
        '''returns the first train in the queue'''
        item = hq.heappop(self.trains)
        return item

    def is_empty(self):
        return len(self.trains) == 0

    def peak_top(self):
        try:
            return self.trains[0]
        except IndexError:
            return None

    def size(self):
        return len(self.trains)


class train:
    def __init__(self, time, id):
        self.arrival = time  # when the train arrived
        self.train_id = id  # for the event log
        self.remaining_crew_time = round(uniform(6, 11), 2)  # how much time left the current crew has
        self.unload_time = round(uniform(3.5, 4.5), 2)  # how long this train will take to unload
        self.remaining_unload_time = self.unload_time  # how long the train has left before it's finished unloading
        self.num_crews = 1  # how many crews this train has had
        self.is_hogged_out = False
        self.crew_time_to_arrive = 0  # how long until the next crew arrives; 0 if there is a currently active crew
        self._now = time  # internal value used to updating the train over time
        self._unloading = False

    def override_train_values(self, unloading_time, crew_hours):
        '''used when the train arrival schedule is passed to the sim; overrides the randomly generated values of train'''
        self.unload_time = unloading_time
        self.remaining_unload_time = unloading_time
        self.remaining_crew_time = crew_hours

    def unload(self, current_time):
        '''called only once per train; used for internal updating and for stat calculations'''
        self._unloading = True

    def is_unloaded(self):
        return self.remaining_unload_time <= 0

    def update_time(self, current_time, pre_loaded_crew_times):
        '''The bread and butter of the train class. This will take a train from any time T and update it to the
        current time in the simulation. With a single call of this function, a train may go through several crews as
        crews hog out and are replaced. This is more likely with larger intervals (simulation time - train's time)'''
        #print(f"Time {round(current_time,2)}: Updating Train {self.train_id}")
        passed_time = round(current_time - self._now, 2)  # how much time has passed since this train was last updated

        while passed_time > 0:
            self._clean_floats()
            if not self.is_hogged_out:
                # train currently has a crew

                if self.remaining_crew_time > passed_time:
                    # the current crew will still be online
                    self.remaining_crew_time -= passed_time
                    if self._unloading:
                        self.remaining_unload_time -= passed_time  # crew spends time unloading if train in loading dock
                    self._now = current_time
                    passed_time = 0

                else:
                    # the current crew will hog out
                    self._now += self.remaining_crew_time  # update "now" to the moment the crew hogged out
                    #print(f"Time {round(self._now, 2)}: train {self.train_id} crew {self.num_crews-1}",
                    #      f"hogged out (SERVER HOGGED)")

                    passed_time -= self.remaining_crew_time  # calculate the remaining time that needs to pass
                    passed_time = round(passed_time, 2)
                    if self._unloading:
                        # train in loading dock, so crew spends time unloading before hogging out
                        self.remaining_unload_time -= self.remaining_crew_time
                    self.remaining_crew_time = 0
                    self.num_crews += 1

                    if pre_loaded_crew_times is None:
                        self.crew_time_to_arrive = self._replacement_crew_arrival_time()  # generate new crew arrival
                    else:
                        try:
                            self.crew_time_to_arrive = pre_loaded_crew_times.pop(0)  # use pre-generated new crew arrival
                        except IndexError:
                            self.crew_time_to_arrive = self._replacement_crew_arrival_time()

                    if self.crew_time_to_arrive > passed_time:
                        # the new crew will not arrive by the current time
                        self.remaining_crew_time = 12 - passed_time  # update remaining crew time to current time
                        self.crew_time_to_arrive -= passed_time
                        self._now = current_time  # "now" is caught up with current time
                        passed_time = 0
                        self.is_hogged_out = True

                    else:
                        # the new crew will arrive by the current time
                        self.remaining_crew_time = 12 - self.crew_time_to_arrive  # update remaining crew time
                        self._now += self.crew_time_to_arrive  # "now" is the moment the new crew arrived
                        #print(f"Time {round(self._now, 2)}: train {self.train_id} replacement crew",
                        #      f"{self.num_crews-1} arrives (SERVER UNHOGGED)")
                        passed_time -= self.crew_time_to_arrive  # there may still be time left to pass before current
                        passed_time = round(passed_time, 2)
                        self.crew_time_to_arrive = 0
                        self.is_hogged_out = False

            else:
                # train is currently waiting for replacement crew
                if self.crew_time_to_arrive > passed_time:
                    # not enough time has passed for the new crew to arrive
                    self.crew_time_to_arrive -= passed_time
                    self.remaining_crew_time -= passed_time
                    self._now = current_time
                    passed_time = 0

                else:
                    # enough time has passed for the new crew to arrive
                    passed_time -= self.crew_time_to_arrive  # there may still be time left to pass before current
                    passed_time = round(passed_time, 2)
                    self.remaining_crew_time -= self.crew_time_to_arrive
                    self._now += self.crew_time_to_arrive
                    #print(f"Time {round(self._now, 2)}: train {self.train_id} replacement crew",
                    #      f"{self.num_crews - 1} arrives (SERVER UNHOGGED)")
                    self.crew_time_to_arrive = 0
                    self.is_hogged_out = False

        self._clean_floats()
        #print(f"Updated Train {self.train_id}.")

    def force_time_update(self, now):
        '''updates the train's internal time without checking for changes in crew or unload time'''
        self._now = round(now, 2)

    def get_train_lifetime(self):
        '''returns how long the train was in the simulation for'''
        return round(self._now - self.arrival, 2)

    def get_train_queue_time(self):
        '''returns how long the train was in queue for'''
        return round(self.time_left_queue - self.arrival, 2)

    def get_num_hogouts(self):
        '''returns the number of times the crew hogged out'''
        return self.num_crews - 1

    def debug(self):
        print(f"Train ({self.arrival})")
        print(f"Current time: {self._now}")
        print(f"Hogged?: {self.is_hogged_out}")
        print(f"Number of Crews: {self.num_crews}")
        print(f"Remaining Crew Time: {self.remaining_crew_time}")
        print(f"Time Until Crew Arrival: {self.crew_time_to_arrive}")
        print()

    def _replacement_crew_arrival_time(self):
        '''randomly determines the new crew's arrival time'''
        return round(uniform(2.5, 3.5), 2)

    def _clean_floats(self):
        '''Rounds floats to nearest 100th'''
        self.crew_time_to_arrive = round(self.crew_time_to_arrive, 2)
        self.remaining_crew_time = round(self.remaining_crew_time, 2)
        self.remaining_unload_time = round(self.remaining_unload_time, 2)

    def __lt__(self, other):
        return self.arrival < other.arrival

    def __gt__(self, other):
        return self.arrival > other.arrival

    def __le__(self, other):
        return self.arrival <= other.arrival

    def __ge__(self, other):
        return self.arrival >= other.arrival

    def __eq__(self, other):
        return self.arrival == other.arrival

    def __ne__(self, other):
        return self.arrival != other.arrival


class statTracker:
    def __init__(self):
        self.loading_status = 0  # 0 = idle, 1 = busy, -1 = hogged out
        self.status_times = [0, 0, 0]
        self.num_trains = 0
        self.time_in_system = []
        self.hog_outs = defaultdict(int)
        self.max_trains_in_queue = 0
        self.queue_time_integral = 0
        self._now = 0
        self._queue = 0

    def report_stats(self):
        print("Statistics")
        print("----------")
        print(f"Total number of trains served: {self.num_trains}")
        print(f"Average time-in-system per train: {round(sum(self.time_in_system) / len(self.time_in_system), 4)}h")
        print(f"Maximum time-in-system per train: {round(max(self.time_in_system), 4)}h")
        print(f"Dock idle percentage: {round(self.status_times[0] / self._now, 4) * 100}%")
        print(f"Dock busy percentage: {round(self.status_times[1] / self._now, 4) * 100}%")
        print(f"Dock hogged-out percentage: {round(self.status_times[-1] / sum(self.status_times), 4) * 100}%")
        print(self.queue_time_integral)
        print(f"Time average of trains in queue: {round(self.queue_time_integral / self._now, 4)}")
        print(f"Maximum number of trains in queue: {self.max_trains_in_queue}")
        self.print_histogram()

    def update_status(self, status_code):
        '''used to change the current status of the loading dock'''
        self.loading_status = status_code

    def pass_time(self, now, queue):
        '''used to total how much time the loading dock spent in each state & for time-average in queue'''
        self.status_times[self.loading_status] += round(now - self._now, 2)
        if self.loading_status == -1:
            # if the loading dock is hogged out, it is also idle
            self.status_times[0] += round(now - self._now, 2)

        if self._queue > 0 and now - self._now > 0:
            print(f"Time {now:.2f}: integral = {self._queue} * {now - self._now:.2f}")
        self.queue_time_integral += self._queue * (now - self._now)
        self._queue = queue
        self._now = now

    def scrape_train_stats(self, tr):
        '''pulls the relevant stats from a train object before it departs'''
        self.num_trains += 1
        self.time_in_system.append(tr.get_train_lifetime())
        self.hog_outs[tr.get_num_hogouts()] += 1

    def print_histogram(self):
        '''prints the histogram of hogouts'''
        print("Histogram of hogout count per train:")
        for index, hogouts in sorted(self.hog_outs.items()):
            print(f"[{index}]: {hogouts}")

    def max_queue(self, trains_in_queue):
        '''updates the max queue size that was reached throughout the simulation'''
        self.max_trains_in_queue = max(self.max_trains_in_queue, trains_in_queue)
