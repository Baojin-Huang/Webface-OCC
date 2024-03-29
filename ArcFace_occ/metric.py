import numpy as np
import mxnet as mx


class AccMetric(mx.metric.EvalMetric):
    def __init__(self):
        self.axis = 1
        super(AccMetric, self).__init__('acc',
                                        axis=self.axis,
                                        output_names=None,
                                        label_names=None)
        self.losses = []
        self.count = 0

    def update(self, labels, preds):
        self.count += 1
        label = labels[0]
        pred_label = preds[2] # 2
        # print('ACC', label.shape, pred_label.shape)
        # print(np.sum(labels[1].asnumpy()<0.9))
        # print(preds)
        if pred_label.shape != label.shape:
            pred_label = mx.ndarray.argmax(pred_label, axis=self.axis)
        pred_label = pred_label.asnumpy().astype('int32').flatten()
        label = label.asnumpy()
        if label.ndim == 2:
            label = label[:, 0]
        label = label.astype('int32').flatten()
        assert label.shape == pred_label.shape
        self.sum_metric += (pred_label.flat == label.flat).sum()
        self.num_inst += len(pred_label.flat)


class Id_LossValueMetric(mx.metric.EvalMetric):
    def __init__(self):
        self.axis = 1
        super(Id_LossValueMetric, self).__init__('ce_lossvalue',
                                              axis=self.axis,
                                              output_names=None,
                                              label_names=None)
        self.losses = []

    def update(self, labels, preds):
        #label = labels[0].asnumpy()
        # print(preds)
        pred = preds[-2].asnumpy() # -2
        loss = pred[0]
        self.sum_metric += loss
        self.num_inst += 1.0
        #gt_label = preds[-2].asnumpy()
        #print(gt_label)

class Mask_LossValueMetric(mx.metric.EvalMetric):
    def __init__(self):
        self.axis = 1
        super(Mask_LossValueMetric, self).__init__('mask_lossvalue',
                                              axis=self.axis,
                                              output_names=None,
                                              label_names=None)
        self.losses = []

    def update(self, labels, preds):
        #label = labels[0].asnumpy()
        pred = preds[-1].asnumpy()
        loss = pred[0]
        self.sum_metric += loss
        self.num_inst += 1.0
        #gt_label = preds[-2].asnumpy()
        #print(gt_label)
