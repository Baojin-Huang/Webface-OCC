# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
'''
Adapted from https://github.com/tornadomeet/ResNet/blob/master/symbol_resnet.py
Original author Wei Wu

Implemented the following paper:

Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun. "Identity Mappings in Deep Residual Networks"
'''
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import sys
import os
import mxnet as mx
import numpy as np
import symbol_utils
import memonger
import sklearn
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import config


def Conv(**kwargs):
    #name = kwargs.get('name')
    #_weight = mx.symbol.Variable(name+'_weight')
    #_bias = mx.symbol.Variable(name+'_bias', lr_mult=2.0, wd_mult=0.0)
    #body = mx.sym.Convolution(weight = _weight, bias = _bias, **kwargs)
    body = mx.sym.Convolution(**kwargs)
    return body


def Act(data, act_type, name):
    if act_type == 'prelu':
        body = mx.sym.LeakyReLU(data=data, act_type='prelu', name=name)
    else:
        body = mx.symbol.Activation(data=data, act_type=act_type, name=name)
    return body


def residual_unit_v1(data, num_filter, stride, dim_match, name, bottle_neck,
                     **kwargs):
    """Return ResNet Unit symbol for building ResNet
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tuple
        Stride used in convolution
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    use_se = kwargs.get('version_se', 1)
    bn_mom = kwargs.get('bn_mom', 0.9)
    workspace = kwargs.get('workspace', 256)
    memonger = kwargs.get('memonger', False)
    act_type = kwargs.get('version_act', 'prelu')
    #print('in unit1')
    if bottle_neck:
        conv1 = Conv(data=data,
                     num_filter=int(num_filter * 0.25),
                     kernel=(1, 1),
                     stride=stride,
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=int(num_filter * 0.25),
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn2')
        act2 = Act(data=bn2, act_type=act_type, name=name + '_relu2')
        conv3 = Conv(data=act2,
                     num_filter=num_filter,
                     kernel=(1, 1),
                     stride=(1, 1),
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv3')
        bn3 = mx.sym.BatchNorm(data=conv3,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn3')

        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn3,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn3 = mx.symbol.broadcast_mul(bn3, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        eps=2e-5,
                                        momentum=bn_mom,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return Act(data=bn3 + shortcut,
                   act_type=act_type,
                   name=name + '_relu3')
    else:
        conv1 = Conv(data=data,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=stride,
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn2')
        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn2,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn2 = mx.symbol.broadcast_mul(bn2, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        momentum=bn_mom,
                                        eps=2e-5,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return Act(data=bn2 + shortcut,
                   act_type=act_type,
                   name=name + '_relu3')


def residual_unit_v1_L(data, num_filter, stride, dim_match, name, bottle_neck,
                       **kwargs):
    """Return ResNet Unit symbol for building ResNet
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tuple
        Stride used in convolution
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    use_se = kwargs.get('version_se', 1)
    bn_mom = kwargs.get('bn_mom', 0.9)
    workspace = kwargs.get('workspace', 256)
    memonger = kwargs.get('memonger', False)
    act_type = kwargs.get('version_act', 'prelu')
    #print('in unit1')
    if bottle_neck:
        conv1 = Conv(data=data,
                     num_filter=int(num_filter * 0.25),
                     kernel=(1, 1),
                     stride=(1, 1),
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=int(num_filter * 0.25),
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn2')
        act2 = Act(data=bn2, act_type=act_type, name=name + '_relu2')
        conv3 = Conv(data=act2,
                     num_filter=num_filter,
                     kernel=(1, 1),
                     stride=stride,
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv3')
        bn3 = mx.sym.BatchNorm(data=conv3,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn3')

        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn3,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn3 = mx.symbol.broadcast_mul(bn3, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        eps=2e-5,
                                        momentum=bn_mom,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return Act(data=bn3 + shortcut,
                   act_type=act_type,
                   name=name + '_relu3')
    else:
        conv1 = Conv(data=data,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn1 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=stride,
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn2 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn2')
        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn2,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn2 = mx.symbol.broadcast_mul(bn2, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        momentum=bn_mom,
                                        eps=2e-5,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return Act(data=bn2 + shortcut,
                   act_type=act_type,
                   name=name + '_relu3')


def residual_unit_v2(data, num_filter, stride, dim_match, name, bottle_neck,
                     **kwargs):
    """Return ResNet Unit symbol for building ResNet
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tuple
        Stride used in convolution
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    use_se = kwargs.get('version_se', 1)
    bn_mom = kwargs.get('bn_mom', 0.9)
    workspace = kwargs.get('workspace', 256)
    memonger = kwargs.get('memonger', False)
    act_type = kwargs.get('version_act', 'prelu')
    #print('in unit2')
    if bottle_neck:
        # the same as https://github.com/facebook/fb.resnet.torch#notes, a bit difference with origin paper
        bn1 = mx.sym.BatchNorm(data=data,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv1 = Conv(data=act1,
                     num_filter=int(num_filter * 0.25),
                     kernel=(1, 1),
                     stride=(1, 1),
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn2')
        act2 = Act(data=bn2, act_type=act_type, name=name + '_relu2')
        conv2 = Conv(data=act2,
                     num_filter=int(num_filter * 0.25),
                     kernel=(3, 3),
                     stride=stride,
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn3 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn3')
        act3 = Act(data=bn3, act_type=act_type, name=name + '_relu3')
        conv3 = Conv(data=act3,
                     num_filter=num_filter,
                     kernel=(1, 1),
                     stride=(1, 1),
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv3')
        if use_se:
            #se begin
            body = mx.sym.Pooling(data=conv3,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            conv3 = mx.symbol.broadcast_mul(conv3, body)
        if dim_match:
            shortcut = data
        else:
            shortcut = Conv(data=act1,
                            num_filter=num_filter,
                            kernel=(1, 1),
                            stride=stride,
                            no_bias=True,
                            workspace=workspace,
                            name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return conv3 + shortcut
    else:
        bn1 = mx.sym.BatchNorm(data=data,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn1')
        act1 = Act(data=bn1, act_type=act_type, name=name + '_relu1')
        conv1 = Conv(data=act1,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=stride,
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               momentum=bn_mom,
                               eps=2e-5,
                               name=name + '_bn2')
        act2 = Act(data=bn2, act_type=act_type, name=name + '_relu2')
        conv2 = Conv(data=act2,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        if use_se:
            #se begin
            body = mx.sym.Pooling(data=conv2,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            conv2 = mx.symbol.broadcast_mul(conv2, body)
        if dim_match:
            shortcut = data
        else:
            shortcut = Conv(data=act1,
                            num_filter=num_filter,
                            kernel=(1, 1),
                            stride=stride,
                            no_bias=True,
                            workspace=workspace,
                            name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return conv2 + shortcut


def residual_unit_v3(data, num_filter, stride, dim_match, name, bottle_neck,
                     **kwargs):
    """Return ResNet Unit symbol for building ResNet
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tuple
        Stride used in convolution
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    use_se = kwargs.get('version_se', 1)
    bn_mom = kwargs.get('bn_mom', 0.9)
    workspace = kwargs.get('workspace', 256)
    memonger = kwargs.get('memonger', False)
    act_type = kwargs.get('version_act', 'prelu')
    #print('in unit3')
    if bottle_neck:
        bn1 = mx.sym.BatchNorm(data=data,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn1')
        conv1 = Conv(data=bn1,
                     num_filter=int(num_filter * 0.25),
                     kernel=(1, 1),
                     stride=(1, 1),
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn2')
        act1 = Act(data=bn2, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=int(num_filter * 0.25),
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn3 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn3')
        act2 = Act(data=bn3, act_type=act_type, name=name + '_relu2')
        conv3 = Conv(data=act2,
                     num_filter=num_filter,
                     kernel=(1, 1),
                     stride=stride,
                     pad=(0, 0),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv3')
        bn4 = mx.sym.BatchNorm(data=conv3,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn4')

        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn4,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn4 = mx.symbol.broadcast_mul(bn4, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        eps=2e-5,
                                        momentum=bn_mom,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        return bn4 + shortcut
    else:
        bn1 = mx.sym.BatchNorm(data=data,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn1')
        conv1 = Conv(data=bn1,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=(1, 1),
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv1')
        bn2 = mx.sym.BatchNorm(data=conv1,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn2')
        act1 = Act(data=bn2, act_type=act_type, name=name + '_relu1')
        conv2 = Conv(data=act1,
                     num_filter=num_filter,
                     kernel=(3, 3),
                     stride=stride,
                     pad=(1, 1),
                     no_bias=True,
                     workspace=workspace,
                     name=name + '_conv2')
        bn3 = mx.sym.BatchNorm(data=conv2,
                               fix_gamma=False,
                               eps=2e-5,
                               momentum=bn_mom,
                               name=name + '_bn3')
        if use_se:
            #se begin
            body = mx.sym.Pooling(data=bn3,
                                  global_pool=True,
                                  kernel=(7, 7),
                                  pool_type='avg',
                                  name=name + '_se_pool1')
            body = Conv(data=body,
                        num_filter=num_filter // 16,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv1",
                        workspace=workspace)
            body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
            body = Conv(data=body,
                        num_filter=num_filter,
                        kernel=(1, 1),
                        stride=(1, 1),
                        pad=(0, 0),
                        name=name + "_se_conv2",
                        workspace=workspace)
            body = mx.symbol.Activation(data=body,
                                        act_type='sigmoid',
                                        name=name + "_se_sigmoid")
            bn3 = mx.symbol.broadcast_mul(bn3, body)
            #se end

        if dim_match:
            shortcut = data
        else:
            conv1sc = Conv(data=data,
                           num_filter=num_filter,
                           kernel=(1, 1),
                           stride=stride,
                           no_bias=True,
                           workspace=workspace,
                           name=name + '_conv1sc')
            shortcut = mx.sym.BatchNorm(data=conv1sc,
                                        fix_gamma=False,
                                        momentum=bn_mom,
                                        eps=2e-5,
                                        name=name + '_sc')
        if memonger:
            shortcut._set_attr(mirror_stage='True')
        # arg_name = shortcut.list_arguments()
        # out_name = shortcut.list_outputs()
        # arg_shape, out_shape, _ = shortcut.infer_shape(data=(1,3,112,112))
        # print({'input' : dict(zip(arg_name, arg_shape)),'output' : dict(zip(out_name, out_shape))})
        return bn3 + shortcut


def residual_unit_v3_x(data, num_filter, stride, dim_match, name, bottle_neck,
                       **kwargs):
    """Return ResNeXt Unit symbol for building ResNeXt
    Parameters
    ----------
    data : str
        Input data
    num_filter : int
        Number of output channels
    bnf : int
        Bottle neck channels factor with regard to num_filter
    stride : tuple
        Stride used in convolution
    dim_match : Boolean
        True means channel number between input and output is the same, otherwise means differ
    name : str
        Base name of the operators
    workspace : int
        Workspace used in convolution operator
    """
    assert (bottle_neck)
    use_se = kwargs.get('version_se', 1)
    bn_mom = kwargs.get('bn_mom', 0.9)
    workspace = kwargs.get('workspace', 256)
    memonger = kwargs.get('memonger', False)
    act_type = kwargs.get('version_act', 'prelu')
    num_group = 32
    #print('in unit3')
    bn1 = mx.sym.BatchNorm(data=data,
                           fix_gamma=False,
                           eps=2e-5,
                           momentum=bn_mom,
                           name=name + '_bn1')
    conv1 = Conv(data=bn1,
                 num_group=num_group,
                 num_filter=int(num_filter * 0.5),
                 kernel=(1, 1),
                 stride=(1, 1),
                 pad=(0, 0),
                 no_bias=True,
                 workspace=workspace,
                 name=name + '_conv1')
    bn2 = mx.sym.BatchNorm(data=conv1,
                           fix_gamma=False,
                           eps=2e-5,
                           momentum=bn_mom,
                           name=name + '_bn2')
    act1 = Act(data=bn2, act_type=act_type, name=name + '_relu1')
    conv2 = Conv(data=act1,
                 num_group=num_group,
                 num_filter=int(num_filter * 0.5),
                 kernel=(3, 3),
                 stride=(1, 1),
                 pad=(1, 1),
                 no_bias=True,
                 workspace=workspace,
                 name=name + '_conv2')
    bn3 = mx.sym.BatchNorm(data=conv2,
                           fix_gamma=False,
                           eps=2e-5,
                           momentum=bn_mom,
                           name=name + '_bn3')
    act2 = Act(data=bn3, act_type=act_type, name=name + '_relu2')
    conv3 = Conv(data=act2,
                 num_filter=num_filter,
                 kernel=(1, 1),
                 stride=stride,
                 pad=(0, 0),
                 no_bias=True,
                 workspace=workspace,
                 name=name + '_conv3')
    bn4 = mx.sym.BatchNorm(data=conv3,
                           fix_gamma=False,
                           eps=2e-5,
                           momentum=bn_mom,
                           name=name + '_bn4')

    if use_se:
        #se begin
        body = mx.sym.Pooling(data=bn4,
                              global_pool=True,
                              kernel=(7, 7),
                              pool_type='avg',
                              name=name + '_se_pool1')
        body = Conv(data=body,
                    num_filter=num_filter // 16,
                    kernel=(1, 1),
                    stride=(1, 1),
                    pad=(0, 0),
                    name=name + "_se_conv1",
                    workspace=workspace)
        body = Act(data=body, act_type=act_type, name=name + '_se_relu1')
        body = Conv(data=body,
                    num_filter=num_filter,
                    kernel=(1, 1),
                    stride=(1, 1),
                    pad=(0, 0),
                    name=name + "_se_conv2",
                    workspace=workspace)
        body = mx.symbol.Activation(data=body,
                                    act_type='sigmoid',
                                    name=name + "_se_sigmoid")
        bn4 = mx.symbol.broadcast_mul(bn4, body)
        #se end

    if dim_match:
        shortcut = data
    else:
        conv1sc = Conv(data=data,
                       num_filter=num_filter,
                       kernel=(1, 1),
                       stride=stride,
                       no_bias=True,
                       workspace=workspace,
                       name=name + '_conv1sc')
        shortcut = mx.sym.BatchNorm(data=conv1sc,
                                    fix_gamma=False,
                                    eps=2e-5,
                                    momentum=bn_mom,
                                    name=name + '_sc')
    if memonger:
        shortcut._set_attr(mirror_stage='True')
    return bn4 + shortcut


def residual_unit(data, num_filter, stride, dim_match, name, bottle_neck,
                  **kwargs):
    uv = kwargs.get('version_unit', 3)
    version_input = kwargs.get('version_input', 1)
    if uv == 1:
        if version_input == 0:
            return residual_unit_v1(data, num_filter, stride, dim_match, name,
                                    bottle_neck, **kwargs)
        else:
            return residual_unit_v1_L(data, num_filter, stride, dim_match,
                                      name, bottle_neck, **kwargs)
    elif uv == 2:
        return residual_unit_v2(data, num_filter, stride, dim_match, name,
                                bottle_neck, **kwargs)
    elif uv == 4:
        return residual_unit_v4(data, num_filter, stride, dim_match, name,
                                bottle_neck, **kwargs)
    else:
        return residual_unit_v3(data, num_filter, stride, dim_match, name,
                                bottle_neck, **kwargs)


def resnet(units, num_stages, filter_list, num_classes, bottle_neck):
    bn_mom = config.bn_mom
    workspace = config.workspace
    kwargs = {
        'version_se': config.net_se,
        'version_input': config.net_input,
        'version_output': config.net_output,
        'version_unit': config.net_unit,
        'version_act': config.net_act,
        'bn_mom': bn_mom,
        'workspace': workspace,
        'memonger': config.memonger,
    }
    """Return ResNet symbol of
    Parameters
    ----------
    units : list
        Number of units in each stage
    num_stages : int
        Number of stage
    filter_list : list
        Channel size of each stage
    num_classes : int
        Ouput size of symbol
    dataset : str
        Dataset type, only cifar10 and imagenet supports
    workspace : int
        Workspace used in convolution operator
    """
    version_se = kwargs.get('version_se', 1)
    version_input = kwargs.get('version_input', 1)
    assert version_input >= 0
    version_output = kwargs.get('version_output', 'E')
    fc_type = version_output
    version_unit = kwargs.get('version_unit', 3)
    act_type = kwargs.get('version_act', 'prelu')
    memonger = kwargs.get('memonger', False)
    print(version_se, version_input, version_output, version_unit, act_type,
          memonger)
    num_unit = len(units)
    assert (num_unit == num_stages)
    data = mx.sym.Variable(name='data')
    # data = mx.sym.Cast(data=data, dtype=np.float16)
    if version_input == 0:
        #data = mx.sym.BatchNorm(data=data, fix_gamma=True, eps=2e-5, momentum=bn_mom, name='bn_data')
        data = mx.sym.identity(data=data, name='id')
        data = data - 127.5
        data = data * 0.0078125
        body = Conv(data=data,
                    num_filter=filter_list[0],
                    kernel=(7, 7),
                    stride=(2, 2),
                    pad=(3, 3),
                    no_bias=True,
                    name="conv0",
                    workspace=workspace)
        body = mx.sym.BatchNorm(data=body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='bn0')
        body = Act(data=body, act_type=act_type, name='relu0')
        #body = mx.sym.Pooling(data=body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')
    elif version_input == 2:
        data = mx.sym.BatchNorm(data=data,
                                fix_gamma=True,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='bn_data')
        body = Conv(data=data,
                    num_filter=filter_list[0],
                    kernel=(3, 3),
                    stride=(1, 1),
                    pad=(1, 1),
                    no_bias=True,
                    name="conv0",
                    workspace=workspace)
        body = mx.sym.BatchNorm(data=body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='bn0')
        body = Act(data=body, act_type=act_type, name='relu0')
    else:
        data = mx.sym.identity(data=data, name='id')
        data = data - 127.5
        data = data * 0.0078125
        body = data
        body = Conv(data=body,
                    num_filter=filter_list[0],
                    kernel=(3, 3),
                    stride=(1, 1),
                    pad=(1, 1),
                    no_bias=True,
                    name="conv0",
                    workspace=workspace)
        body = mx.sym.BatchNorm(data=body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='bn0')
        body = Act(data=body, act_type=act_type, name='relu0')
    
    for i in range(num_stages):
        #if version_input==0:
        #  body = residual_unit(body, filter_list[i+1], (1 if i==0 else 2, 1 if i==0 else 2), False,
        #                       name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, **kwargs)
        #else:
        #  body = residual_unit(body, filter_list[i+1], (2, 2), False,
        #    name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, **kwargs)
        # if i==num_stages-1:
        #     body = mx.sym.Cast(data=body, dtype=np.float32)
        body = residual_unit(body,
                             filter_list[i + 1], (2, 2),
                             False,
                             name='stage%d_unit%d' % (i + 1, 1),
                             bottle_neck=bottle_neck,
                             **kwargs)
        for j in range(units[i] - 1):
            body = residual_unit(body,
                                 filter_list[i + 1], (1, 1),
                                 True,
                                 name='stage%d_unit%d' % (i + 1, j + 2),
                                 bottle_neck=bottle_neck,
                                 **kwargs)
    
    de_body = mx.symbol.slice(body,begin=(None,0,None,None), end=(None,256,None,None))
    de_body = mx.sym.Deconvolution(data=de_body,num_filter=256,kernel=(4, 4),stride=(2, 2),pad=(1, 1),name="de_conv1")
    de_body = mx.sym.BatchNorm(data=de_body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='de_bnd1')
    de_body = Act(data=de_body, act_type=act_type, name='de_relud1') 
    de_body0 = mx.symbol.slice(de_body,begin=(None,128,None,None), end=(None,256,None,None))

    de_body = mx.sym.Deconvolution(data=de_body,num_filter=128,kernel=(4, 4),stride=(2, 2),pad=(1, 1),name="de_conv2")
    de_body = mx.sym.BatchNorm(data=de_body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='de_bnd2')
    de_body = Act(data=de_body, act_type=act_type, name='de_relud2')
    de_body1 = mx.symbol.slice(de_body,begin=(None,64,None,None), end=(None,128,None,None))

    de_body = mx.sym.Deconvolution(data=de_body,num_filter=64,kernel=(4, 4),stride=(2, 2),pad=(1, 1),name="de_conv3")
    de_body = mx.sym.BatchNorm(data=de_body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='de_bnd3')
    de_body = Act(data=de_body, act_type=act_type, name='de_relud3')
    de_body2 = mx.symbol.slice(de_body,begin=(None,32,None,None), end=(None,64,None,None))

    de_body = mx.sym.Deconvolution(data=de_body,num_filter=32,kernel=(4, 4),stride=(2, 2),pad=(1, 1),name="de_conv4")
    de_body = mx.sym.BatchNorm(data=de_body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='de_bnd4')
    de_body_temp = Act(data=de_body, act_type=act_type, name='de_relud4')
    de_body3 = mx.symbol.slice(de_body_temp,begin=(None,16,None,None), end=(None,32,None,None))
    de_body = Conv(data=de_body_temp,
                    num_filter=1,
                    kernel=(7, 7),
                    stride=(1, 1),
                    pad=(3, 3),
                    no_bias=True,
                    name="dd_conv5",
                    workspace=workspace) 
    de_body = mx.sym.BatchNorm(data=de_body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='de_bnd5')
    weight = mx.symbol.Activation(data=de_body, act_type='sigmoid', name="pw_sigmoid")

    de_body = mx.symbol.broadcast_mul(weight, de_body_temp)

    de_body = residual_unit(de_body,
                                 32, (1, 1),
                                 False,
                                 name='stage%d_unit%d' % (5, 1),
                                 bottle_neck=bottle_neck,
                                 **kwargs)
    # arg_name = de_body.list_arguments()
    # out_name = de_body.list_outputs()
    # arg_shape, out_shape, _ = de_body.infer_shape(data=(1,3,112,112))
    # print({'input' : dict(zip(arg_name, arg_shape)),'output' : dict(zip(out_name, out_shape))})
    de_body = mx.sym.Pooling(data=de_body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')
    
    de_body = mx.symbol.concat(de_body,de_body2,dim=1)
    de_body = residual_unit(de_body,
                                 64, (1, 1),
                                 False,
                                 name='stage%d_unit%d' % (5, 2),
                                 bottle_neck=bottle_neck,
                                 **kwargs)
    de_body = mx.sym.Pooling(data=de_body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')

    de_body = mx.symbol.concat(de_body,de_body1,dim=1)
    de_body = residual_unit(de_body,
                                 128, (1, 1),
                                 False,
                                 name='stage%d_unit%d' % (5, 3),
                                 bottle_neck=bottle_neck,
                                 **kwargs)
    de_body = mx.sym.Pooling(data=de_body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')

    de_body = mx.symbol.concat(de_body,de_body0,dim=1)
    de_body = residual_unit(de_body,
                                 256, (1, 1),
                                 False,
                                 name='stage%d_unit%d' % (5, 4),
                                 bottle_neck=bottle_neck,
                                 **kwargs)
    de_body = mx.sym.Pooling(data=de_body, kernel=(3, 3), stride=(2,2), pad=(1,1), pool_type='max')

    # de_body = Conv(data=de_body,
    #                 num_filter=int(num_classes),
    #                 kernel=(3, 3),
    #                 stride=(1, 1),
    #                 pad=(1, 1),
    #                 no_bias=True,
    #                 name="ww_conv1",
    #                 workspace=workspace)
    # de_body = mx.sym.BatchNorm(data=de_body,
    #                             fix_gamma=False,
    #                             eps=2e-5,
    #                             momentum=bn_mom,
    #                             name='ww_bnd1')
    # de_body = Act(data=de_body, act_type=act_type, name='ww_relud1')
    # de_body = Conv(data=de_body,
    #                 num_filter=int(num_classes),
    #                 kernel=(3, 3),
    #                 stride=(1, 1),
    #                 pad=(1, 1),
    #                 no_bias=True,
    #                 name="ww_conv2",
    #                 workspace=workspace)
    # de_body = mx.sym.BatchNorm(data=de_body,
    #                             fix_gamma=False,
    #                             eps=2e-5,
    #                             momentum=bn_mom,
    #                             name='ww_bnd2')
    # de_body = Act(data=de_body, act_type=act_type, name='ww_relud2')

    # de_body = Conv(data=de_body,
    #                 num_filter=1,
    #                 kernel=(1, 1),
    #                 stride=(1, 1),
    #                 pad=(1, 1),
    #                 no_bias=True,
    #                 name="ww_conv3",
    #                 workspace=workspace)

    weight_f = de_body
    # weight_f = Conv(data=weight_f,
    #                 num_filter=num_classes,
    #                 kernel=(3, 3),
    #                 stride=(1, 1),
    #                 pad=(1, 1),
    #                 no_bias=True,
    #                 name="act_conv2",
    #                 workspace=workspace)
    # weight_f = mx.sym.BatchNorm(data=weight_f,
    #                             fix_gamma=False,
    #                             eps=2e-5,
    #                             momentum=bn_mom,
    #                             name='act_bnd2')
    # weight_f = Act(data=weight_f, act_type=act_type, name='act_relud2')
    weight_f = 1 + mx.symbol.Activation(data=weight_f, act_type='sigmoid', name="act_sigmoid")
    # weight_f = mx.symbol.repeat(weight_f, repeats=num_classes, axis=1)
    
    # arg_name = weight.list_arguments()
    # out_name = weight.list_outputs()
    # arg_shape, out_shape, _ = weight.infer_shape(data=(1,3,112,112))
    # print({'input' : dict(zip(arg_name, arg_shape)),'output' : dict(zip(out_name, out_shape))})
    # mx.sym.exp
    body = mx.symbol.slice(body,begin=(None,256,None,None), end=(None,512,None,None))
    body_weight = mx.symbol.broadcast_mul(weight_f, body)
    body_add = body + body_weight

    body_add = Conv(data=body_add,
                    num_filter=int(num_classes)//32,
                    kernel=(3, 3),
                    stride=(1, 1),
                    pad=(1, 1),
                    no_bias=True,
                    name="add_conv1",
                    workspace=workspace)
    body_add = mx.sym.BatchNorm(data=body_add,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='add_bnd1')
    body_add = Act(data=body_add, act_type=act_type, name='add_sigmoid1')

    body_add = Conv(data=body_add,
                    num_filter=int(num_classes)//2,
                    kernel=(3, 3),
                    stride=(1, 1),
                    pad=(1, 1),
                    no_bias=True,
                    name="add_conv2",
                    workspace=workspace)
    body_add = mx.sym.BatchNorm(data=body_add,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='add_bnd2')
    body_add = Act(data=body_add, act_type='sigmoid', name='add_sigmoid2')
    body = mx.symbol.broadcast_mul(body_add, body) + mx.symbol.broadcast_mul(1-body_add, body_weight)


    for i in range(4,num_stages):
        #if version_input==0:
        #  body = residual_unit(body, filter_list[i+1], (1 if i==0 else 2, 1 if i==0 else 2), False,
        #                       name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, **kwargs)
        #else:
        #  body = residual_unit(body, filter_list[i+1], (2, 2), False,
        #    name='stage%d_unit%d' % (i + 1, 1), bottle_neck=bottle_neck, **kwargs)
        body = residual_unit(body,
                             filter_list[i + 1], (2, 2),
                             False,
                             name='stage%d_unit%d' % (i + 1, 1),
                             bottle_neck=bottle_neck,
                             **kwargs)
        for j in range(units[i] - 1):
            body = residual_unit(body,
                                 filter_list[i + 1], (1, 1),
                                 True,
                                 name='stage%d_unit%d' % (i + 1, j + 2),
                                 bottle_neck=bottle_neck,
                                 **kwargs)

    if bottle_neck:
        body = Conv(data=body,
                    num_filter=512,
                    kernel=(1, 1),
                    stride=(1, 1),
                    pad=(0, 0),
                    no_bias=True,
                    name="convd",
                    workspace=workspace)
        body = mx.sym.BatchNorm(data=body,
                                fix_gamma=False,
                                eps=2e-5,
                                momentum=bn_mom,
                                name='bnd')
        body = Act(data=body, act_type=act_type, name='relud')
    
    
    # weight = mx.symbol.Activation(data=de_body, act_type='sigmoid', name="pw_sigmoid")
    # min_ = mx.symbol.min(weight,axis=[2,3],keepdims= 1)
    # min_ = mx.symbol.repeat(min_, repeats=112, axis=2)
    # min_ = mx.symbol.repeat(min_, repeats=112, axis=3)
    # max_ = mx.symbol.max(weight,axis=[2,3],keepdims= 1)
    # max_ = mx.symbol.repeat(max_, repeats=112, axis=2)
    # max_ = mx.symbol.repeat(max_, repeats=112, axis=3)
    # weight = (weight - min_)/(max_ - min_)

    fc1 = symbol_utils.get_fc1(body, num_classes, fc_type)
    return fc1,weight


def get_symbol():
    """
    Adapted from https://github.com/tornadomeet/ResNet/blob/master/train_resnet.py
    Original author Wei Wu
    """
    num_classes = config.emb_size
    num_layers = config.num_layers
    if num_layers >= 500:
        filter_list = [64, 256, 512, 1024, 2048]
        bottle_neck = True
    else:
        filter_list = [64, 64, 128, 256, 512]
        bottle_neck = False
    num_stages = 4
    if num_layers == 18:
        units = [2, 2, 2, 2]
    elif num_layers == 34:
        units = [3, 4, 6, 3]
    elif num_layers == 49:
        units = [3, 4, 14, 3]
    elif num_layers == 50:
        units = [3, 4, 14, 3]
    elif num_layers == 74:
        units = [3, 6, 24, 3]
    elif num_layers == 90:
        units = [3, 8, 30, 3]
    elif num_layers == 98:
        units = [3, 4, 38, 3]
    elif num_layers == 99:
        units = [3, 8, 35, 3]
    elif num_layers == 100:
        units = [3, 13, 30, 3]
    elif num_layers == 134:
        units = [3, 10, 50, 3]
    elif num_layers == 136:
        units = [3, 13, 48, 3]
    elif num_layers == 140:
        units = [3, 15, 48, 3]
    elif num_layers == 124:
        units = [3, 13, 40, 5]
    elif num_layers == 160:
        units = [3, 24, 49, 3]
    elif num_layers == 101:
        units = [3, 4, 23, 3]
    elif num_layers == 152:
        units = [3, 8, 36, 3]
    elif num_layers == 200:
        units = [3, 24, 36, 3]
    elif num_layers == 269:
        units = [3, 30, 48, 8]
    else:
        raise ValueError(
            "no experiments done on num_layers {}, you can do it yourself".
            format(num_layers))

    net = resnet(units=units,
                 num_stages=num_stages,
                 filter_list=filter_list,
                 num_classes=num_classes,
                 bottle_neck=bottle_neck)

    if config.memonger:
        dshape = (config.per_batch_size, config.image_shape[2],
                  config.image_shape[0], config.image_shape[1])
        net_mem_planned = memonger.search_plan(net, data=dshape)
        old_cost = memonger.get_cost(net, data=dshape)
        new_cost = memonger.get_cost(net_mem_planned, data=dshape)

        print('Old feature map cost=%d MB' % old_cost)
        print('New feature map cost=%d MB' % new_cost)
        net = net_mem_planned
    return net
