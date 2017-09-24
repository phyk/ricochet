from keras.models import Sequential
from keras.layers.core import Dense, Dropout, Activation
from keras.optimizers import Adam
import numpy as np
import random as rand
import ricochet.environment as envi
import ricochet.hyperparameter as hp
import matplotlib.pyplot as plt
import atexit
from collections import deque


class stats_collector():
    collect_step_counts = True
    collect_n_last_games = 0
    collect_rewards = True
    steps = []
    games = deque(maxlen=collect_n_last_games)
    reward = []
    diction = {'steps': (collect_step_counts, steps), 'games': (collect_n_last_games > 0, games),
               'rewards': (collect_rewards, reward)}
    
    def reset(self):
        self.steps.clear()
        self.reward.clear()

    def collect(self, name, val):
        if self.diction[name][0]:
            self.diction[name][1].append(val)

    def plt(self, name):
        if self.diction[name][0]:
            plt.plot(self.diction[name][1])
            plt.show()


class debugger():
    render = False
    log_epoch = 100

    def reset(self):
        pass


stats = stats_collector()
debug = debugger()


class Q_network():
    def __init__(self, environment):
        self.memory = deque(maxlen=2000)
        self.env = environment
        self.model = Sequential()
        self.model = Sequential()
        self.model.add(Dense(164, activation='relu', input_shape=(self.env.flattened_input_size,)))
        # model.add(Dropout(0.2)) I'm not using dropout, but maybe you wanna give it a try?

        self.model.add(Dense(150, activation='relu'))
        # model.add(Dropout(0.2))

        self.model.add(Dense(self.env.action_size, activation='softmax'))

        self.model.compile(loss='mse', optimizer=Adam(lr=hp.lr))

        self.e = hp.e_start

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        if np.random.rand() <= self.e:
            return rand.randrange(self.env.action_size)
        act_values = self.model.predict(state)
        return np.argmax(act_values[0])

    def replay(self, batch_size):
        mini_batch = rand.sample(self.memory, batch_size)
        for state, action, reward, next_state, done in mini_batch:
            target = reward
            if not done:
                target = reward + hp.gamma * \
                       np.max(self.model.predict(next_state)[0])
            target_f = self.model.predict(state)
            target_f[0][action] = target
            self.model.fit(state, target_f, epochs=1, verbose=0)
        if self.e > hp.e_min:
            self.e -= hp.e_decay


@atexit.register
def termination():
    if stats.collect_step_counts:
        plt.plot(stats.steps)
        plt.show()


if __name__ == "__main__":
    # initialize gym environment and the agent
    env = envi.environment(4)
    agent = Q_network(env)
    # Iterate the game
    for epoch in range(hp.epochs):
        s = env.reset(flattened=True)
        for steps in range(500):
            a = agent.act(s)
            s1, r, d, _ = env.step(a, flattened=True)
            agent.remember(s, a, r, s1, d)
            s = s1
            if d:
                stats.collect('steps', steps)
                if epoch > 0 and epoch % debug.log_epoch == 0:
                    print("episode: {}/{}, score: {}".format(epoch, hp.epochs, steps),
                          "avg. score last {} = {}".format(debug.log_epoch, np.mean(stats.steps[-debug.log_epoch:])),
                          "epsilon = {}".format(agent.e))
                break
        agent.replay(32)
    stats.plt('steps')
