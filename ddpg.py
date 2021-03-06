
# coding: utf-8

# In[1]:


import numpy as np
import tensorflow as tf


# In[16]:


#import nbimporter
from Actor import ActorNetwork
from Critic import CriticNetwork
from ReplayBuffer import ReplayBuffer
from ou_noise import OUNoise


# In[17]:


# Hyper Parameters:
REPLAY_BUFFER_SIZE = 2000000
REPLAY_START_SIZE = 128
BATCH_SIZE = 128
GAMMA = 0.97


# In[ ]:


class DDPG:
    
    def __init__(self, env, state_dim=None):
        self.name = 'DDPG' # name for uploading results
        self.environment = env
        # Randomly initialize actor network and critic network
        # along with their target networks
        if state_dim:
            self.state_dim = state_dim
            print (self.state_dim)
        else:
            self.state_dim = env.observation_space.shape[0]
        self.action_dim = env.action_space.shape[0]

        self.sess = tf.InteractiveSession()

        self.actor_network = ActorNetwork(self.sess,self.state_dim,self.action_dim)
        self.critic_network = CriticNetwork(self.sess,self.state_dim,self.action_dim)
        
        # initialize replay buffer
        self.replay_buffer = ReplayBuffer(REPLAY_BUFFER_SIZE)

        # Initialize a random process the Ornstein-Uhlenbeck process for action exploration
        self.exploration_noise = OUNoise(self.action_dim)
        
        # Flag to signal save
        self.not_saved = True
        
        #For normalisation
        self.state_mean = 0
        self.state_std = 1
        self.target_mean = 0
        self.target_std = 1
        
    def train(self):
        #print "train step",self.time_step
        # Sample a random minibatch of N transitions from replay buffer
        minibatch = self.replay_buffer.get_batch(BATCH_SIZE)
        state_batch = np.asarray([data[0] for data in minibatch])
        action_batch = np.asarray([data[1] for data in minibatch])
        reward_batch = np.asarray([data[2] for data in minibatch])
        next_state_batch = np.asarray([data[3] for data in minibatch])
        done_batch = np.asarray([data[4] for data in minibatch])
        
        #For Normalisation
        states = np.array(state_batch)
        targets = np.array(next_state_batch)
        self.state_mean = states.mean(axis=0)
        self.state_std = states.std(axis=0) + 0.00000001
        self.target_mean = targets.mean(axis=0)
        self.target_std = targets.std(axis=0) + 0.00000001
        states = (state_batch - self.state_mean)/self.state_std
        targets = (next_state_batch - self.target_mean)/self.target_std
        state_batch = states.tolist()
        next_state_batch = targets.tolist()

        # for action_dim = 1
        action_batch = np.resize(action_batch,[BATCH_SIZE,self.action_dim])

        # Calculate y_batch
        next_action_batch = self.actor_network.target_actions(next_state_batch)
        q_value_batch = self.critic_network.target_q(next_state_batch,next_action_batch)
        y_batch = []  
        for i in range(len(minibatch)): 
            if done_batch[i]:
                y_batch.append(reward_batch[i])
            else :
                y_batch.append(reward_batch[i] + GAMMA * q_value_batch[i])
        y_batch = np.resize(y_batch,[BATCH_SIZE,1])
        # Update critic by minimizing the loss L
        self.critic_network.train(y_batch,state_batch,action_batch)

        # Update the actor policy using the sampled gradient:
        action_batch_for_gradients = self.actor_network.actions(state_batch)
        q_gradient_batch = self.critic_network.gradients(state_batch,action_batch_for_gradients)

        self.actor_network.train(q_gradient_batch,state_batch)

        # Update the target networks
        self.actor_network.update_target()
        self.critic_network.update_target()

        
    def noise_action(self,state):
        # Select action a_t according to the current policy and exploration noise
        
        # Normalising first
        state = np.array(state)
        state = (state - self.state_mean)/self.state_std
        state = state.tolist()
        
        action = self.actor_network.action(state)
#         print ("State-: ", state)
#         print ("Action-: ", action)
        return action+self.exploration_noise.noise()
    
    
    def action(self,state):
        # Normalising first
        state = np.array(state)
        state = (state - self.state_mean)/self.state_std
        state = state.tolist()
        # Taking action
        action = self.actor_network.action(state)
        return action
    
    
    def perceive(self,state,action,reward,next_state,done,episode):
        # Store transition (s_t,a_t,r_t,s_{t+1}) in replay buffer
        self.replay_buffer.add(state,action,reward,next_state,done)

        # Store transitions to replay start size then start training
        if self.replay_buffer.count() >  REPLAY_START_SIZE:
            self.train()

        self.time_step = self.critic_network.time_step
        if episode % 20 == 0:  #self.time_step % 400 == 0:
            if self.not_saved:
                self.actor_network.save_network(episode) #(self.time_step)
                self.critic_network.save_network(episode) #(self.time_step)
                self.not_saved = False
        else:
            self.not_saved = True

        # Re-iniitialize the random process when an episode ends
        if done:
            self.exploration_noise.reset()

