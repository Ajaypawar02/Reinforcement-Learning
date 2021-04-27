import numpy as np
import gym
import torch as T
import torch.nn as nn
import torch.nn.functional as F 
import torch.optim as optim 

class DeepQNetwork(nn.Module):
    def __init__(self,lr,input_dims,fc1_dims,fc2_dims,n_actions):
        super(DeepQNetwork,self).__init__()
        self.input_dims = input_dims
        self.fc1_dims = fc1_dims
        self.fc2_dims = fc2_dims
        self.n_actions = n_actions
        self.fc1 = nn.Linear(*self.input_dims, self.fc1_dims)
        self.fc2 = nn.Linear(self.fc1_dims, self.fc2_dims)
        self.fc3 = nn.Linear(self.fc2_dims, self.n_actions)
        self.optimizer = optim.Adam(self.parameters(), lr = lr)
        self.loss = nn.MSELoss()
        self.device = T.device('cuda:0' if T.cuda.is_available() else 'cpu')
        self.to(self.device)

    def forward(self, state):
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        actions = self.fc3(x)

        return actions
    
class Agent():
    def __init__(self, gamma, epsilon,lr,input_dims,batch_size,n_actions,max_mem_size = 100000,eps_end = 0.01, eps_dec = 5e-4):
        self.gamma = gamma
        self.epsilon = epsilon
        self.lr = lr
        self.batch_size = batch_size
        #self.n_actions = n_actions
        self.mem_size = max_mem_size
        self.eps_min = eps_end
        self.eps_dec = eps_dec
        self.action_space = [i for i in range(n_actions)]
        self.mem_cntr = 0


        self.Q_eval = DeepQNetwork(self.lr, n_actions = n_actions, input_dims = input_dims,fc1_dims = 256,fc2_dims = 256)
        self.state_memory = np.zeros((self.mem_size, *input_dims), dtype = np.float32)
        self.new_state_memory = np.zeros((self.mem_size, *input_dims), dtype = np.float32)
        self.action_memory = np.zeros(self.mem_size, dtype = np.int32)
        self.reward_memory = np.zeros(self.mem_size, dtype = np.float32)
        self.terminal_memory = np.zeros(self.mem_size, dtype = np.bool)
        #self.mem_cntr += 1

    def store_transition(self,state, action, reward, state_, done):
        index = self.mem_cntr % self.mem_size
        #print(index)
        self.state_memory[index] = state
        self.new_state_memory[index] = state_
        self.reward_memory[index] = reward
        self.action_memory[index] = action
        self.terminal_memory[index] = done
        self.mem_cntr += 1

    def choose_actions(self ,observation):
        if np.random.random() > self.epsilon:
            state = T.tensor([observation],dtype= T.float32).to(self.Q_eval.device)
            
            actions = self.Q_eval.forward(state)
            action = T.argmax(actions).item()
        else:
            action = np.random.choice(self.action_space) 

        return action

    def learn(self):
        if self.mem_cntr < self.batch_size:
            return

        self.Q_eval.optimizer.zero_grad()

        max_mem = min(self.mem_cntr, self.mem_size)
        batch = np.random.choice(max_mem, self.batch_size, replace = False)
        batch_index = np.arange(self.batch_size, dtype = np.int32)
        state_batch = T.tensor(self.state_memory[batch]).to(self.Q_eval.device)
        new_state_batch = T.tensor(self.new_state_memory[batch]).to(self.Q_eval.device)
        reward_batch = T.tensor(self.reward_memory[batch]).to(self.Q_eval.device)
        terminal_batch = T.tensor(self.terminal_memory[batch]).to(self.Q_eval.device)
        action_batch = self.action_memory[batch]

        q_eval = self.Q_eval.forward(state_batch)[batch_index, action_batch]
        q_next = self.Q_eval.forward(new_state_batch)
        q_next[terminal_batch] = 0.0

        q_target = reward_batch + self.gamma * T.max(q_next, dim = 1)[0]

        loss = self.Q_eval.loss(q_target,q_eval).to(self.Q_eval.device)
        loss.backward()
        self.Q_eval.optimizer.step()

        self.epsilon  = self.epsilon - self.eps_dec if self.epsilon > self.eps_min \
                        else self.eps_min

        

if __name__ == "__main__":
    env = gym.make('CartPole-v1').unwrapped
    
    agent = Agent(gamma = 0.99,epsilon = 1.0, batch_size = 64, n_actions = env.action_space.n,
                  eps_end = 0.01, input_dims = env.observation_space.shape,lr = 0.003)

    scores, eps_history = [], []
    n_episodes = 100

    for i in range(n_episodes):
        score = 0
        done = False
        observation = env.reset()
        env.render()
        while not done:
            action = agent.choose_actions(observation)
            observation_ , reward, done , info = env.step(action)
            score += reward
            agent.store_transition(observation,action,reward,observation_, done)
            agent.learn()
            observation = observation_
        scores.append(score)
        eps_history.append(agent.epsilon)
        avg_score = np.mean(scores[-100:])

        print('episode', i, 'scores%2f' % score,
              'average score %.2f' % avg_score,
               'epsilon %.2f' % agent.epsilon)
        

