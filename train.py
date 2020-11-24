import data_structures as ds
import sim_setup as ss

SIMULATION_TIME = 100000
ARRIVAL_AVERAGE = 10


def arrival_event(time, train, queue_size):
    print(f"Time {round(time, 2)}: train {train.train_id} arrival for {round(train.unload_time, 2)}h of unloading,",
          f"crew {train.num_crews - 1} with {round(train.remaining_crew_time, 2)}h before hogout (Q={queue_size - 1})")


def enter_dock(time, train):
    print(f"Time {round(time, 2)}: train {train.train_id} entering dock for {round(train.unload_time, 2)}h of unloading,",
          f"crew {train.num_crews - 1} with {round(train.remaining_crew_time, 2)}h before hogout")


def cant_enter(time, train):
    print(f"Time {round(time, 2)}: train {train.train_id} crew {train.num_crews - 1} hasn't arrived yet, cannot enter",
          f"dock (SERVER HOGGED)")


def depart(time, train, queue_size):
    print(f"Time {round(time, 2)}: train {train.train_id} departing (Q={queue_size})")


if __name__ == "__main__":
    #args = ss.get_args()
    #args = ["-s", "schedule.txt", "traveltimes.txt"]
    args = ["7", "50000"]
    if args[0] == "-s":
        arrival_schedule = open(args[1], 'r')
        events = ss.parse_train_arrival_file(arrival_schedule)
        arrival_schedule.close()

        new_crew_times = open(args[2], 'r')
        preloaded_crew_times = ss.parse_crew_arrival_file(new_crew_times)
        new_crew_times.close()

    else:
        ARRIVAL_AVERAGE = int(args[0])
        SIMULATION_TIME = int(args[1])
        events = ss.generate_arrival_events(SIMULATION_TIME, ARRIVAL_AVERAGE)
        preloaded_crew_times = None

    train_queue = ds.trainQueue()
    stats = ds.statTracker()
    now = 0
    loading = None

    while now < SIMULATION_TIME or not events.is_empty() or not train_queue.is_empty() or loading is not None:
        stats.pass_time(now, train_queue.size())
        stats.max_queue(train_queue.size())
        first_train = train_queue.peak_top()
        next_event = events.peak_top()

        if next_event is None:
            next_event = ds.train(SIMULATION_TIME*2, -1)  # creates a "ghost train" that doesn't really exist.
            # the point of this is to prevent conditions that use "next_event" from throwing an error,
            # but it doesn't change the outcome of the sim since time 2*SIM_TIME will never occur

        if loading is None:
            # loading dock is empty
            stats.update_status(0)  # set loading dock status to "idle"

            if train_queue.is_empty():
                # there is no train anywhere, skip until next arrival
                if events.is_empty():
                    # the simulation has finished early, skip to end
                    break
                else:
                    events.pop()  # the resulting event is already stored in next_event
                    train_queue.enqueue(next_event)  # add the newly arrived train to the queue
                    now = next_event.arrival  # update "now" to arrival time of next train
                    #arrival_event(now, next_event, train_queue.size())
                    continue

            first_train.update_time(now, preloaded_crew_times)  # catch up the first train to the current time

            '''
            3 possible scenarios:
             - front train is hogged out, but the next train arrives before the front train's next crew arrives
             - front train is hogged out, and its next crew arrives before the next train arrives
             - front train is not hogged out, so it moves to the loading dock (then loop to below 3 scenarios)
            '''

            if first_train.is_hogged_out:
                # loading is empty, but the first train in the queue has no crew
                stats.update_status(-1)  # set loading status to "hogged out"
                #cant_enter(now, first_train)

                if next_event.arrival < now + first_train.crew_time_to_arrive:
                    # the next train arrival will occur before the front train gets a new crew
                    events.pop()  # the resulting event is already stored in next_event
                    train_queue.enqueue(next_event)  # add the newly arrived train to the queue
                    now = next_event.arrival  # update "now" to arrival time of next train
                    first_train.update_time(now, preloaded_crew_times)  # update the train at front of queue
                    #arrival_event(now, next_event, train_queue.size())
                    continue
                else:
                    # the front train will get a new crew before the next arrival event
                    now += first_train.crew_time_to_arrive  # update "now" to arrival of new crew
                    first_train.update_time(now, preloaded_crew_times)  # replacement crew arrives
                    loading = train_queue.dequeue()  # first train is moved to loading dock with new crew
                    loading.unload(now)  # tell the crew to start unloading
                    continue

            else:
                # loading is empty, and the first train is ready to move to loading
                loading = train_queue.dequeue()  # first train is moved to loading dock
                loading.unload(now)  # tell the crew to start unloading
                #enter_dock(now, loading)  # reports that the train entered dock
                continue

        else:
            # there is a train in the loading dock
            stats.update_status(1)  # set loading dock status to "busy"
            '''
            3 possible scenarios:
             - next train arrives before the loading train unloads
             - loading train unloads before next train arrives
             - loading train hogs out before next train arrives and before it unloads
            '''

            '''
            if loading train hogs out . . .
            2 possible scenarios:
             - next train arrives before loading dock's train gets new crew
             - loading dock's train gets new crew before next train arrives (then loop back to above 3 scenarios)
            '''

            if loading.is_hogged_out:
                # there is a train in loading, but it's hogged out
                stats.update_status(-1)  # set loading dock status to "hogged out"

                if next_event.arrival < now + loading.crew_time_to_arrive:
                    # the next train arrival will occur before the loading dock train gets new crew
                    events.pop()  # the resulting event is already stored in next_event
                    train_queue.enqueue(next_event)  # add the newly arrived train to the queue
                    now = next_event.arrival  # update "now" to arrival time of next train
                    loading.update_time(now, preloaded_crew_times)  # update the train in loading
                    #arrival_event(now, next_event, train_queue.size())
                    continue
                else:
                    # the train in loading dock will get new crew before next arrival event
                    now += loading.crew_time_to_arrive  # skip to time when new crew arrives
                    loading.update_time(now, preloaded_crew_times)  # update loading dock train to reflect time passage
                    continue

            else:
                # there is a train in loading, and it's ready to unload

                if next_event.arrival < min(now + loading.remaining_unload_time, now + loading.remaining_crew_time):
                    # the next train arrives before the loading dock train finishes unloading or hogs out
                    events.pop()  # the resulting event is already stored in next_event
                    train_queue.enqueue(next_event)  # add the newly arrived train to the queue
                    now = next_event.arrival  # update "now" to arrival time of next train
                    loading.update_time(now, preloaded_crew_times)  # update the train in loading
                    #arrival_event(now, next_event, train_queue.size())
                    continue

                elif loading.remaining_unload_time < loading.remaining_crew_time:
                    # the loading dock train will unload before it hogs out
                    now += loading.remaining_unload_time  # update "now" to when the train finishes unloading
                    loading.force_time_update(now)
                    #depart(now, loading, train_queue.size())
                    stats.scrape_train_stats(loading)
                    loading = None  # train departs
                    continue

                else:
                    # the loading dock train will hog out before it finishes unloading
                    now += loading.remaining_crew_time  # update "now" to when the crew hogs out
                    loading.update_time(now, preloaded_crew_times)  # update loading dock train
                    continue

    print(f"Time {now:.2f}: simulation ended")
    print()
    stats.report_stats()

