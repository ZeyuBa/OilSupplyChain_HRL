import numpy as np
import matplotlib.pyplot as plt
a=np.load("cost_HRL_5.npy")
for i in range(len(a)):
    if (i+1) %30==0:
        print(sum(a[i-29:i]))
        #plt.plot(a[i-29:i])
#plt.plot(a[0:29])
#plt.show()