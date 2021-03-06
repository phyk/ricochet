import datetime
import json
import os
from pathlib import Path

import numpy as np
from net.env_handler import Environment

import game as the_game
import helper as hlp
import hyperparameter as hyperparameter
from gui import gui_train as status_gui
from net.the_brain import Agent, RandomAgent, stats


class Handler:
    def __init__(self, name, version, conv, worker=None, feeder=None, hyperparams=None):
        hlp.to_wrkdir()
        self.gui = None
        self.hp = hyperparams
        if hyperparams is None:
            self.hp = hyperparameter.AgentsHyperparameters()
        self.the_environment = Environment(conv, the_game.Environment(the_game.grid_size))
        self.conv = conv
        self.training = False
        self.finished = False
        self.save = True
        self.name = name
        self.version = version
        self.agent = None
        self.randomAgent = None
        self.worker = worker
        self.feeder = feeder
        self.minimum = self.hp.MINIMUM_CAPTURE_THRESH
        self.folder = Path("models/" + self.name)
        self.min_folder = Path(str(self.folder) + "/" + str(self.version) + "/local min")
        self.cur_ts = datetime.datetime.now()
        self.stopped_early = 0
        self.wait_for_next_early = 0

    def set_hps(self, hyperparams):
        self.hp = hyperparams
        self.agent.update_learning_rate(self.hp.get_attr("LEARNING_RATE"))

    def initialize(self):
        self.agent = Agent(self, conv=self.conv, action_count=self.the_environment.get_action_cnt(),
                           state_count=self.the_environment.get_state_cnt(),
                           grid_size=self.the_environment.get_grid_size(), dims=self.the_environment.get_dims(),
                           worker=self.worker, feeder=self.feeder)
        self.randomAgent = RandomAgent(self, self.the_environment.get_action_cnt())

    def start_training(self, board_style):
        print("performing Random Agent")
        self.agent.brain.model.summary()
        while not self.randomAgent.memory.isFull():
            self.the_environment.run(self.randomAgent, board_style)

        self.agent.memory.samples = self.randomAgent.memory.samples
        self.randomAgent = None

        self.training = True
        self.finished = False
        self.save = True
        if not os.path.exists(self.min_folder):
            os.makedirs(self.min_folder)
        epoch = 0
        self.cur_ts = datetime.datetime.now()
        print("Starting Training")
        while epoch < self.hp.EPOCHS and self.training:
            epoch += 1
            print(epoch, end=' ', flush=True)
            steps, reward = self.the_environment.run(self.agent, board_style, epoch=epoch)
            stats.collect('steps', steps)
            stats.collect('rewards', reward)
            if epoch % self.hp.get_attr('DEBUG_LOG_EPOCHS') == 0:
                game_steps = []
                game_rewards = []
                avg_train_steps = np.mean(stats.steps[-self.hp.get_attr('DEBUG_LOG_EPOCHS'):])
                poller_len = self.hp.get_attr('DEBUG_LOG_EPOCHS')
                for i in range(poller_len):
                    g_steps, g_rewards = self.the_environment.play_game('old', self.agent, board_style=board_style)
                    game_steps.append(g_steps)
                    game_rewards.append(g_rewards)
                avg_game_steps = np.mean(game_steps)

                if avg_game_steps < self.minimum:
                    self.agent.brain.model.save(str(self.min_folder) + "/worker_" + str(avg_game_steps) + ".h5")
                    self.agent.brain.model_.save(str(self.min_folder) + "/feeder_" + str(avg_game_steps) + ".h5")
                    self.minimum = avg_game_steps

                print("avg. steps training = {0}".format(avg_train_steps))
                print("avg. reward = {0}".format(np.mean(game_rewards)))
                print("episode: {}/{}, steps: {}".format(epoch, self.hp.EPOCHS, steps),
                      "avg. steps last {} finishes = {}".format(poller_len, avg_game_steps),
                      "epsilon = {}".format(self.agent.epsilon))
                print("--------------------------------------------------------------------------------")

                if self.gui is not None:
                    self.gui.add_data_point(epoch, avg_game_steps, avg_train_steps)
                    self.gui.plot()
                stats.collect('big_steps', avg_game_steps)
                if hasattr(self.hp, "LEARNING_RATE_MAX") and len(stats.big_steps) > self.hp.LEARNING_RATE_EARLY_STOP:
                    if self.wait_for_next_early < self.hp.LEARNING_RATE_EARLY_STOP:
                        self.wait_for_next_early += 1
                    else:
                        start = -self.hp.LEARNING_RATE_EARLY_STOP
                        first = stats.big_steps[start]
                        early_stop = True
                        for i in range(start, -1):
                            print(stats.big_steps[i], first)
                            if stats.big_steps[i] < first:
                                early_stop = False
                                break
                        if early_stop:
                            self.stopped_early += 1
                            new_lr = self.hp.LEARNING_RATE_MAX / (self.stopped_early * 2)
                            if new_lr < self.hp.LEARNING_RATE_MIN:
                                new_lr = self.hp.LEARNING_RATE_MIN
                            self.agent.update_learning_rate(new_lr)
                            print(f"new learning rate = {new_lr}")
                            self.wait_for_next_early = 0
                stats.steps.clear()

            if epoch % self.hp.get_attr('DEBUG_SNAPSHOT') == 0:
                self.save_model(epoch)

        if self.save:
            self.save_model(epoch)
        self.finished = True
        print("finished training")

    def save_model(self, epochs_done):
        folder = str(self.folder)
        vers = str(self.version)
        my_file = Path(folder + "/" + vers + "/worker.h5")
        my_file_2 = Path(folder + "/" + vers + "/feeder.h5")
        self.agent.brain.model.save(my_file)
        self.agent.brain.model_.save(my_file_2)
        np.save(folder + "/" + vers + "/stats", np.array(stats.big_steps))
        with open(folder + "/" + vers + "/summary.txt", "w") as sum:
            self.agent.brain.model.summary()
            print(f"model: {self.agent.brain.model.to_json()}", file=sum)
            end = datetime.datetime.now()
            print(f"start: {self.cur_ts}, stop: {end}", file=sum)
            print(f"ran: {(end - self.cur_ts)} on {epochs_done} epochs.", file=sum)
        with open(folder + "/" + vers + "/hp.txt", 'w') as outfile:
            json.dump(self.hp.__dict__, outfile)
        self.gui.save_plot_to_disk(folder + "/" + vers + "/plot")
        print("saved model")

    def make_status_gui(self):
        self.gui = status_gui.Status(self)

    def stop_training(self):
        print("Stopping Training")
        self.save = False
        self.training = False

    def pause_training(self):
        print("Pausing Training")
        self.save = True
        self.training = False

    def predict_one(self, s, target=False):
        return self.agent.brain.predictOne(s, target)

    def play_game(self, env_on, max_r):
        r = 0
        min_acts = self.hp.MAX_STEPS
        out_steps, out_total_reward, out_actions = [], [], []
        while r <= max_r:
            steps, total_reward, actions = self.the_environment.play_game('mcts', self.agent, env_on=env_on,
                                                                          return_actions=True, ran=r)
            if len(actions) < min_acts:
                min_acts = len(actions)
                out_steps, out_total_reward, out_actions = steps, total_reward, actions
            r += 0.002
        for a in out_actions:
            print(the_game.print_action(a), end=' ')
        return out_steps, out_total_reward, out_actions
