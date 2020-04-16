import Agents
import Environments
from argparse import ArgumentParser
import uuid
import datetime
import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from tools import *


def check_savability(destination, dictionary):
    """sanity check: try dumping a file on the disk and check it is not too large"""
    temp_name = "/".join([destination, "temp_dump.todelete"])
    try:
        with open(temp_name, 'wb') as f:
            cpickle.dump(dictionary, f)
    except OverflowError:
        return False
    finally:
        os.remove(temp_name)
    return True


def save_dictionary(destination, dictionary, filename):
    """pickle a dictionary and save it to the disk"""

    temp_name = "/".join([destination, filename])

    # if the filename already exists
    while os.path.exists(temp_name):
        temp_name += "_bis"

    # try saving the data
    try:
        with open(temp_name, 'wb') as f:
            cpickle.dump(dictionary, f)
    except:
        print("ERROR: saving the data to disk failed")
        return False

    # try reloading the data to ensure it was correctly saved
    try:
        with open(temp_name, 'rb') as f:
            cpickle.load(f)
    except:
        print("ERROR: saving the data to disk failed (impossible to reload it")
        return False

    return True


def generate_sensorimotor_data(agent, environment, explo_type, k, dest_data="dataset", disp=True):
    """
    Generates a sensorimotor dataset and save it in <dest_data>/dataset_<explo_type>.pkl.
    k sensorimotor transitions are generated by drawing random motor configurations and environment shifts for each sensorimotor experience.

    Inputs:
        agent : the agent generating the motor configurations and egocentric sensor positions
        environment - the environment generating the environment shifts and the sensations associated with the holistic sensor positions
        explo_type - type of exploration, which changes how the shifts are generated
                     MM: the shift is always 0
                     MEM: a different shift is drawn for the first and second sensorimotor couple of each transition
                     MME: the same random shift is used for both sensorimotor pairs of each transition
        k - number of transitions to generate
        dest_data - directory where to save the data
        disp - display the data generated data

    Output:
        The generated dataset is saved in <dest_data>/dataset_<explo_type>.pkl as a dictionary with the following structure:
        transitions = {"motor_t": np.array(n_transitions, agent.n_motors),
                       "sensor_t": np.array(n_transitions, environment.n_sensations),
                       "shift_t": np.array(n_transitions, 2)2,
                       "motor_tp": np.array(n_transitions, agent.n_motors),
                       "sensor_tp": np.array(n_transitions, environment.n_sensations),
                       "shift_tp": np.array(n_transitions, 2),
                       "grid_motor": np.array(agent.size_regular_grid, agent.n_motors),
                       "grid_pos": np.array(agent.size_regular_grid, 2)
                       }
    """

    print("generating {} data... ".format(explo_type))

    # prepare the data dictionary
    transitions = {"motor_t": np.full((k, agent.n_motors), np.nan),
                   "sensor_t": np.full((k, environment.n_sensations), np.nan),
                   "shift_t": np.full((k, 2), np.nan),
                   "motor_tp": np.full((k, agent.n_motors), np.nan),
                   "sensor_tp": np.full((k, environment.n_sensations), np.nan),
                   "shift_tp": np.full((k, 2), np.nan),
                   "grid_motor": np.full((agent.size_regular_grid, agent.n_motors), np.nan),
                   "grid_pos": np.full((agent.size_regular_grid, 2), np.nan)}

    if check_savability(dest_data, transitions) is False:
        print("ERROR: the dataset is too large to pickle - reduce the number of transitions, sensations, or motors")
        return False

    # generate k motor states and sensor positions
    motor_t, ego_pos_t = agent.generate_random_sampling(k)
    motor_tp, ego_pos_tp = agent.generate_random_sampling(k)

    # generate k shifts of the environment
    if explo_type is 'MEM':
        shifts_t = environment.generate_shift(k)
        shifts_tp = environment.generate_shift(k)
    elif explo_type is 'MM':
        shifts_t = environment.generate_shift(k, static=True)  # use environment.generate_shift to get the correct data type
        shifts_tp = shifts_t
    elif explo_type is 'MME':
        shifts_t = environment.generate_shift(k)
        shifts_tp = shifts_t
    else:
        print("ERROR: wrong type of exploration - use 'MM', 'MEM', or 'MME'")

    # compute the holistic position of the sensor
    holi_pos_t = ego_pos_t + shifts_t
    holi_pos_tp = ego_pos_tp + shifts_tp

    # get the corresponding sensations
    sensations_t = environment.get_sensation_at_position(holi_pos_t, display=disp)
    sensations_tp = environment.get_sensation_at_position(holi_pos_tp, display=disp)

    if len(np.argwhere((np.isnan(sensations_t[:, 0])) & (np.isnan(sensations_tp[:, 0])))[:, 0]) > 0:
        print("ERROR: not all sensations are valid - consider re-running the data generation")
        return False

    # generate a regular grid of motor configurations and sensor egocentric positions for evaluation
    grid_motor, grid_pos = agent.generate_regular_sampling()

    # fill the dictionary
    transitions["motor_t"] = motor_t
    transitions["sensor_t"] = sensations_t
    transitions["shift_t"] = shifts_t
    transitions["motor_tp"] = motor_tp
    transitions["sensor_tp"] = sensations_tp
    transitions["shift_tp"] = shifts_tp
    transitions["grid_motor"] = grid_motor
    transitions["grid_pos"] = grid_pos

    save_dictionary(dest_data, transitions, "dataset_{}.pkl".format(explo_type))


def save_simulation(directory, parse, trial):
    """save a UUID for the simulation"""

    dictionary = {"UUID": uuid.uuid4().hex,
                  "Time": datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
                  "Nbr transitions": parse.n_transitions,
                  "Type simulation": parse.type_simu,
                  "Nbr runs": parse.n_runs,
                  "Trial": trial,
                  "Destination": directory,
                  "code commit hash": get_git_hash()}
    try:
        with open(directory + "/generation_params.txt", "w") as f:
            json.dump(dictionary, f, indent=2)
    except:
        print("ERROR: saving generation_params.txt in {} failed".format(directory))
        return False
    return True


def display_samples(dir_data, run_index, explo_type, n=24):
    """
    Display random samples from a dataset.
    Inputs:
        dir_data - directory of the dataset
        explo_type - type of exploration to consider
        run_index - index of sub-dataset to plot from
        n - number of random samples to display
    """

    # check the data_directory exists
    check_directory_exists(dir_data)

    data_directory = dir_data + "/dataset{:03}".format(run_index)
    data_file = data_directory + "/dataset_" + explo_type + ".pkl"

    # load data
    transitions = load_sensorimotor_transitions(data_file)

    # check the type of environment that generated the data
    with open(data_directory + "/environment_params.txt", "r") as f:
        dictionary = json.load(f)
    type_env = dictionary["type"]

    n_sensory_inputs = transitions["sensor_t"].shape[0]

    fig = plt.figure(data_file, figsize=(15, 1))

    if type_env == "GridWorld":

        transitions = normalize_data(transitions)

        for i in range(n):
            # create axes
            ax = fig.add_subplot(1, n, i + 1)

            # draw a sample
            index = np.random.randint(n_sensory_inputs)
            vector = transitions["sensor_t"][index, :]

            # reshape as an image
            image = 0.5 * np.reshape(vector, (-1, 1)) + 0.5

            # display
            ax.imshow(image)
            ax.axis("off")

    elif type_env == "3dRoom":

        for i in range(n):

            # create axes
            ax = fig.add_subplot(1, n, i+1)

            # draw a sample
            index = np.random.randint(n_sensory_inputs)
            image = transitions["sensor_t"][index, :]

            # reshape as an image
            image = np.reshape(image, (int(np.sqrt(np.size(image) / 3)),
                                       int(np.sqrt(np.size(image) / 3)),
                                       3)) / 255

            # display
            ax.imshow(image)
            ax.axis("off")

    plt.show()

    return fig


if __name__ == "__main__":

    # parser
    parser = ArgumentParser()
    parser.add_argument("-n", "--n_transitions", dest="n_transitions", help="number of transitions", type=int, default=150000)
    parser.add_argument("-t", "--type", dest="type_simu", help="type of simulation",
                        choices=["gridexplorer3dof", "gridexplorer6dof", "armroom3dof", "armroom6dof"], required=True)
    parser.add_argument("-r", "--n_runs", dest="n_runs", help="number of independent datasets generated", type=int, default=1)
    parser.add_argument("-d", "--dir_data", dest="dir_data", help="directory where to save the data", required=True)
    parser.add_argument("-v", "--visual", dest="display_exploration", help="flag to turn the online display on or off", action="store_true")
    #
    args = parser.parse_args()
    n_transitions = args.n_transitions
    type_simu = args.type_simu
    n_runs = args.n_runs
    dir_data = args.dir_data
    display_exploration = args.display_exploration

    # create the data directory
    create_directory(dir_data)

    # iterate over the runs
    for trial in range(n_runs):

        # subdirectory for the trial
        dir_data_trial = "/".join([dir_data, "dataset{:03}".format(trial)])

        # skip the trials already existing
        if os.path.exists(dir_data_trial):
            # TODO: check that folder is actually complete (in case of crash, the last run might have stopped before the end)
            print("> trial {} already exists; skipped".format(dir_data_trial))
            continue

        print("[ENVIRONMENT {} >> data saved in {}]".format(trial, dir_data_trial))

        # create the trial subdirectory
        create_directory(dir_data_trial, safe=False)

        # create the agent and environment according to the type of exploration
        if type_simu == "gridexplorer3dof":
            my_agent = Agents.GridExplorer3dof()
            my_environment = Environments.GridWorld()
        #
        elif type_simu == "gridexplorer6dof":
            my_agent = Agents.GridExplorer6dof()
            my_environment = Environments.GridWorld()
        #
        elif type_simu == "armroom3dof":
            my_agent = Agents.HingeArm3dof()  # working space of radius 1.5 in an environment of size size 7
            my_environment = Environments.GQNBulletRoom()
        #
        elif type_simu == "armroom6dof":
            my_agent = Agents.HingeArm6dof()  # working space of radius 1.5 in an environment of size size 7
            my_environment = Environments.GQNBulletRoom()
        #
        else:
            print("ERROR: invalid type of simulation - use 'gridexplorer3dof', 'gridexplorer6dof', 'armroom3dof', or 'armroom6dof'")
            sys.exit()

        # save the agent, environment, and simulation on disk
        my_agent.save(dir_data_trial)
        my_environment.save(dir_data_trial)
        save_simulation(dir_data_trial, args, trial)

        # run the three types of exploration: MEM, MM, MME
        generate_sensorimotor_data(my_agent, my_environment, "MEM", n_transitions, dir_data_trial, disp=display_exploration)
        generate_sensorimotor_data(my_agent, my_environment, "MM",  n_transitions, dir_data_trial, disp=display_exploration)
        generate_sensorimotor_data(my_agent, my_environment, "MME", n_transitions, dir_data_trial, disp=display_exploration)

        # clean
        my_environment.destroy()

    plt.ion()

    index_subdataset = 0
    for exploration_type in ["MEM", "MM", "MME"]:
        fh = display_samples(dir_data, index_subdataset, exploration_type, n=24)
        fh.savefig(dir_data + "/sensory_samples_" + exploration_type + "_dataset" + str(index_subdataset) + ".png")
        fh.savefig(dir_data + "/sensory_samples_" + exploration_type + "_dataset" + str(index_subdataset) + ".svg")

    input("Press any key to exit the program.")
