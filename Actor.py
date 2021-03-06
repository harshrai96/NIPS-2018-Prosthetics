
# coding: utf-8

# In[31]:


import tensorflow as tf 
from tensorflow.contrib.layers.python.layers import batch_norm as batch_norm
import numpy as np
import math


# In[32]:


# Hyper Parameters
LAYER1_SIZE = 512
LAYER2_SIZE = 256
LEARNING_RATE = 3e-4
TAU = 0.001
BATCH_SIZE = 128


# In[33]:


class HiddenLayer:
    def __init__(self, shape, f, use_bias=True):
        '''
        shape: [input_layer, output_layer]
        f: fan-in size
        '''
        self.W = tf.Variable(tf.random_normal(shape=shape), -1/math.sqrt(f), 1/math.sqrt(f))
        self.params = [self.W]
        self.use_bias = use_bias
        if use_bias:
            self.b = tf.Variable(tf.random_uniform(shape=[shape[1]]), -1/math.sqrt(f), 1/math.sqrt(f))
            self.params.append(self.b)

    def forward(self, X):
        if self.use_bias:
            a = tf.matmul(X, self.W) + self.b
        else:
            a = tf.matmul(X, self.W)
        return self.f(a)
    


# In[34]:


class ActorNetwork:
    
    def __init__(self,sess,state_dim,action_dim):
        self.sess = sess
        self.state_dim = state_dim
        self.action_dim = action_dim
        # creating the network for actor
        self.state_input,        self.action_output,        self.params,        self.is_training = self.create_network(state_dim,action_dim)
        # creating a target network
        self.target_state_input,        self.target_action_output,        self.target_update,        self.target_is_training = self.create_target_network(state_dim,action_dim,self.params)
        # define training rules
        self.create_training_method()
        # Initial Initialisation
        self.sess.run(tf.initialize_all_variables())
        # Target Update
        self.update_target()
        # Loading from checkpoint
        self.load_network()
    
    
    def create_training_method(self):
        self.q_gradient_input = tf.placeholder(tf.float32,shape=[None,self.action_dim])
        self.parameters_gradients = tf.gradients(self.action_output,self.params,-self.q_gradient_input)
        self.optimizer = tf.train.AdamOptimizer(LEARNING_RATE).apply_gradients(zip(self.parameters_gradients,self.params))

    
    def create_network(self, state_dim, action_dim):
        layer1_size = LAYER1_SIZE
        layer2_size = LAYER2_SIZE
        state_input = tf.placeholder(tf.float32,shape=[None,state_dim]) # input to the network
        is_training = tf.placeholder(tf.bool) # training/testing flag
        # Creating layers
        W1 = self.variable([state_dim,layer1_size], state_dim)
        b1 = self.variable([layer1_size], state_dim)
        W2 = self.variable([layer1_size,layer2_size], layer1_size)
        b2 = self.variable([layer2_size], layer1_size)
        W3 = tf.Variable(tf.random_normal([layer2_size,action_dim],-3e-3,3e-3))
        b3 = tf.Variable(tf.random_normal([action_dim],-3e-3,3e-3))
        # Feed Forward and Normalisation
        layer0_bn = self.batch_norm_layer(state_input,training_phase=is_training,scope_bn='batch_norm_0',activation=tf.identity)
        layer1 = tf.matmul(layer0_bn,W1) + b1
        layer1_bn = self.batch_norm_layer(layer1,training_phase=is_training,scope_bn='batch_norm_1',activation=tf.nn.selu)
        layer2 = tf.matmul(layer1_bn,W2) + b2
        layer2_bn = self.batch_norm_layer(layer2,training_phase=is_training,scope_bn='batch_norm_2',activation=tf.nn.selu)
        # Output Layer Evaluation
        action_output = tf.tanh(tf.matmul(layer2_bn,W3) + b3)
        return state_input,action_output,[W1,b1,W2,b2,W3,b3],is_training
        
        
    def create_target_network(self,state_dim,action_dim,params):
        state_input = tf.placeholder(tf.float32,shape=[None,state_dim]) # input to the network
        is_training = tf.placeholder(tf.bool) # training/testing flag
        ema = tf.train.ExponentialMovingAverage(decay=1-TAU) # for "soft" update
        target_update = ema.apply(params)
        target_net = [ema.average(x) for x in params]
        # Feed Forward and Normalisation
        layer0_bn = self.batch_norm_layer(state_input,training_phase=is_training,scope_bn='target_batch_norm_0',activation=tf.identity)
        layer1 = tf.matmul(layer0_bn,target_net[0]) + target_net[1]
        layer1_bn = self.batch_norm_layer(layer1,training_phase=is_training,scope_bn='target_batch_norm_1',activation=tf.nn.selu)
        layer2 = tf.matmul(layer1_bn,target_net[2]) + target_net[3]
        layer2_bn = self.batch_norm_layer(layer2,training_phase=is_training,scope_bn='target_batch_norm_2',activation=tf.nn.selu)
        # Output Layer Evaluation
        action_output = tf.tanh(tf.matmul(layer2_bn,target_net[4]) + target_net[5])
        return state_input,action_output,target_update,is_training
    
    
    def variable(self,shape,f=None):
        if f:
            return tf.Variable(tf.random_normal(shape,-1/math.sqrt(f),1/math.sqrt(f)))
        return tf.Variable(tf.random_normal(shape))
    
    
    def update_target(self):
        self.sess.run(self.target_update)
        
        
    def train(self,q_gradient_batch,state_batch):
        self.sess.run(self.optimizer,
                      feed_dict={self.q_gradient_input:q_gradient_batch,
                                self.state_input:state_batch,
                                self.is_training: True
                                })
        
        
    def actions(self,state_batch):
        return self.sess.run(self.action_output,
                             feed_dict={self.state_input:state_batch,
                                        self.is_training: True
                                        })
    
    
    def action(self,state):
        return self.sess.run(self.action_output,
                             feed_dict={self.state_input:[state],
                                        self.is_training: False
                                        })[0]
    
    
    def target_actions(self,state_batch):
        return self.sess.run(self.target_action_output,
                             feed_dict={self.target_state_input: state_batch,
                                        self.target_is_training: True
                                        })
    
    
    def batch_norm_layer(self,x,training_phase,scope_bn,activation=None):
        return tf.cond(training_phase, 
                        lambda: tf.contrib.layers.batch_norm(x, activation_fn=activation, center=True, scale=True,
                        updates_collections=None,is_training=True, reuse=None,scope=scope_bn,decay=0.9, epsilon=1e-5),
                        lambda: tf.contrib.layers.batch_norm(x, activation_fn =activation, center=True, scale=True,
                        updates_collections=None,is_training=False, reuse=True,scope=scope_bn,decay=0.9, epsilon=1e-5)
                      )
    
    
    def load_network(self):
        self.saver = tf.train.Saver()
        checkpoint = tf.train.get_checkpoint_state("saved_actor_networks")
        if checkpoint and checkpoint.model_checkpoint_path:
            self.saver.restore(self.sess, checkpoint.model_checkpoint_path)
            print ("Successfully loaded:", checkpoint.model_checkpoint_path)
        else:
            print ("Could not find old network weights")
            
            
    def save_network(self,time_step):
        print ('save actor-network...',time_step)
        self.saver.save(self.sess, 'saved_actor_networks/' + 'actor-network', global_step = time_step)

