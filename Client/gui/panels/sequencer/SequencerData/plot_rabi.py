
import yaml

from matplotlib import pyplot as plt

THRESHOLD = 1.5

f = open("rabi1.yaml")
data = yaml.load(f)
print(data)
new_dict = dict()
for key in data.keys():
 	one_freq = 0
 	total_freq = 0
 	for count in data[key]:
         if count > THRESHOLD:
             one_freq += data[key][count]
             total_freq += data[key][count]
    print(key)
    new_dict[float(key[:-2])] = one_freq / total_freq

print(new_dict)

plt.plot(new_dict.keys(), new_dict.values(), ".")
plt.show()

f.close()