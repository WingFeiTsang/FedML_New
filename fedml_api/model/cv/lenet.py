import torch
import torch.nn as nn
import torch.nn.functional as F


class LeNet(torch.nn.Module):
    def __init__(self):
        super(LeNet, self).__init__()
        self.conv1 = torch.nn.Conv2d(1, 6, kernel_size=5, padding=2)
        self.conv2 = torch.nn.Conv2d(6, 16, kernel_size=5)
        self.max_pooling = nn.MaxPool2d(2, stride=2)
        self.flatten = nn.Flatten()
        self.fc1 = torch.nn.Linear(16 * 5 * 5, 120)
        self.fc2 = torch.nn.Linear(120, 84)
        self.fc3 = torch.nn.Linear(84, 10)

    def forward(self, x):
        x = x.reshape(-1, 1, 28, 28)
        x = self.conv1(x)
        x = F.relu(x)
        x = self.max_pooling(x)
        x = self.conv2(x)
        x = F.relu(x)
        x = self.max_pooling(x)
        # x = self.flatten(x)
        x = x.view(x.size()[0], -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x
