# OCI-AutoScaleInstances
Auto scale the VM instances of OCI based on time frame ( ex:  10:20-10:25; start at - 10:20 and stop at - 10:25 )
Welcome to the Scheduled Auto Scaling Script for OCI (Oracle Cloud Infrastructure).

The AutoScaleInstances script: A single Auto Scaling script for all OCI resources that support power on/off operations.
# Supported services
Compute VMs: On/Off

################################
Create a free-tier compute instance using the Autonomous Linux 7.8 image
Create a Dynamic Group called Autoscaling and add the OCID of your instance to the group, using this command:
ANY {instance.id = 'your_OCID_of_your_Compute_Instance'}
Create a root level policy, giving your dynamic group permission to manage all resources in tenancy:
allow dynamic-group Autoscaling to manage all-resources in tenancy
Login to your instance using an SSH connection
run the following commands:
wget https://raw.githubusercontent.com/AnykeyNL/OCI-AutoScale/master/install.sh
bash install.sh
If this is the first time you are using the Autoscaling script, go to the OCI-Autoscale directory and run the following command:
python3 CreateNameSpaces.py

The Install script will configure the time zone to European Central Time (CET). If you want to operate in a difference timezone, run the command:

sudo timedatectl set-timezone Europe/Amsterdam
The instance is now all setup and will run for every 1 minute on power on operations.

### How to use
To control what to scale up/down or power on/off, you need to create a predefined tag called Schedule. If you want to localize this, that is possible in the script. For the predefined tag, you need entries for the days of the week, weekdays, weekends and anyday. The tags names are case sensitive!

A single resource can contain multiple tags. A Weekend/Weekday tag overrules an AnyDay tag. A specific day of the week tag (ie. Monday) overrules all other tags.
The value of the tag needs to contain any number of values seperated by ','

Schedule.AnyDay : 10:25-10:30;10:31-10:33;10:35-10:36;.....
![image](https://user-images.githubusercontent.com/26667063/136828324-ba46929c-5f65-4a23-b3ae-3da20dc4ae89.png)


 

