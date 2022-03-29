#!/home/opc/py36env/bin/python
#################################################################################################################
#################################################################################################################
# OCI - Scheduled Auto Scaling Script
# Copyright (c) 2016, 2020, Oracle and/or its affiliates.  All rights reserved.
# This software is licensed to you under the Universal Permissive License (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl
#
# Written by: Allabakshu Shaik
#
#################################################################################################################
# Application Command line parameters
#
#   -t config  - Config file section to use (tenancy profile)
#   -ip        - Use Instance Principals for Authentication
#   -dt        - Use Instance Principals with delegation token for cloud shell
#   -a         - Action - All,Up,Down
#   -tag       - Tag - Default Schedule
#   -rg        - Filter on Region
#   -ic        - include compartment ocid
#   -ec        - exclude compartment ocid
#   -ignrtime  - ignore region time zone
#   -ignormysql- ignore mysql execution
#   -printocid - print ocid of object
#   -topic     - topic to sent summary
#   -h         - help
#
#################################################################################################################
import oci
import datetime
import calendar
import threading
import time
import sys
import argparse
import os

# You can modify / translate the tag names used by this script - case sensitive!!!
AnyDay = "AnyDay"
Weekend = "Weekend"
WeekDay = "WeekDay"
Version = "2021.08.17"

# ============== CONFIGURE THIS SECTION ======================
# OCI Configuration
# ============================================================

ComputeShutdownMethod = "SOFTSTOP"
LogLevel = "ALL"  # Use ALL or ERRORS. When set to ERRORS only a notification will be published if error occurs
TopicID = ""  # Enter Topic OCID if you want the script to publish a message about the scaling actions

AlternativeWeekend = False  # Set to True is your weekend is Friday/Saturday
RateLimitDelay = 2  # Time in seconds to wait before retry of operation

##########################################################################
# Get current host time and utc on execution
##########################################################################
current_host_time = datetime.datetime.today()
current_utc_time = datetime.datetime.utcnow()


##########################################################################
# Print header centered
##########################################################################
def print_header(name):
    chars = int(90)
    MakeLog("")
    MakeLog('#' * chars)
    MakeLog("#" + name.center(chars - 2, " ") + "#")
    MakeLog('#' * chars)


##########################################################################
# Get Current Hour per the region
##########################################################################
def get_current_hour(region, ignore_region_time=False):
    if region[:2] == 'eu':
        timezdiff = 2
    elif region[:2] == 'uk':
        timezdiff = 0
    elif region == 'af-johannesburg-1':
        timezdiff = 2
    elif region == 'ap-chiyoda-1':
        timezdiff = 9
    elif region == 'ap-chuncheon-1':
        timezdiff = 9
    elif region == 'ap-hyderabad-1':
        timezdiff = 5.5
    elif region == 'ap-melbourne-1':
        timezdiff = 10
    elif region == 'ap-mumbai-1':
        timezdiff = 5.5
    elif region == 'ap-osaka-1':
        timezdiff = 9
    elif region == 'ap-seoul-1':
        timezdiff = 9
    elif region == 'ap-singapore-1':
        timezdiff = 8
    elif region == 'ap-sydney-1':
        timezdiff = 10
    elif region == 'ap-tokyo-1':
        timezdiff = 9
    elif region == 'ca-montreal-1':
        timezdiff = -4
    elif region == 'ca-toronto-1':
        timezdiff = -4
    elif region == 'il-jerusalem-1':
        timezdiff = 3
    elif region == 'me-abudhabi-1':
        timezdiff = 4
    elif region == 'me-dubai-1':
        timezdiff = 4
    elif region == 'me-jeddah-1':
        timezdiff = 3
    elif region == 'sa-santiago-1':
        timezdiff = -4
    elif region == 'sa-saopaulo-1':
        timezdiff = -3
    elif region == 'sa-vinhedo-1':
        timezdiff = -3
    elif region == 'us-ashburn-1':
        timezdiff = -4
    elif region == 'us-gov-ashburn-1':
        timezdiff = -4
    elif region == 'us-gov-chicago-1':
        timezdiff = -5
    elif region == 'us-gov-fortworth-1':
        timezdiff = -5
    elif region == 'us-gov-fortworth-2':
        timezdiff = -5
    elif region == 'us-gov-phoenix-1':
        timezdiff = -7
    elif region == 'us-gov-sterling-1 ':
        timezdiff = -4
    elif region == 'us-gov-sterling-2':
        timezdiff = -4
    elif region == 'us-langley-1':
        timezdiff = -5
    elif region == 'us-luke-1':
        timezdiff = -7
    elif region == 'us-phoenix-1':
        timezdiff = -7
    elif region == 'us-sanjose-1':
        timezdiff = -7
    else:
        timezdiff = 0

    # Get current host time
    current_time = current_host_time

    # if need to use region time
    if not ignore_region_time:
        current_time = current_utc_time + datetime.timedelta(hours=timezdiff)

    # get the variables to return
    iDayOfWeek = current_time.weekday()  # Day of week as a number
    iDay = calendar.day_name[iDayOfWeek]  # Day of week as string
    iCurrentHour = current_time.hour

    return iDayOfWeek, iDay, iCurrentHour


##########################################################################
# Create signer for Authentication
# Input - config_profile and is_instance_principals and is_delegation_token
# Output - config and signer objects
##########################################################################
def create_signer(config_profile, is_instance_principals, is_delegation_token):

    # if instance principals authentications
    if is_instance_principals:
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            config = {'region': signer.region, 'tenancy': signer.tenancy_id}
            return config, signer

        except Exception:
            print_header("Error obtaining instance principals certificate, aborting")
            raise SystemExit

    # -----------------------------
    # Delegation Token
    # -----------------------------
    elif is_delegation_token:

        try:
            # check if env variables OCI_CONFIG_FILE, OCI_CONFIG_PROFILE exist and use them
            env_config_file = os.environ.get('OCI_CONFIG_FILE')
            env_config_section = os.environ.get('OCI_CONFIG_PROFILE')

            # check if file exist
            if env_config_file is None or env_config_section is None:
                MakeLog("*** OCI_CONFIG_FILE and OCI_CONFIG_PROFILE env variables not found, abort. ***")
                MakeLog("")
                raise SystemExit

            config = oci.config.from_file(env_config_file, env_config_section)
            delegation_token_location = config["delegation_token_file"]

            with open(delegation_token_location, 'r') as delegation_token_file:
                delegation_token = delegation_token_file.read().strip()
                # get signer from delegation token
                signer = oci.auth.signers.InstancePrincipalsDelegationTokenSigner(delegation_token=delegation_token)

                return config, signer

        except KeyError:
            MakeLog("* Key Error obtaining delegation_token_file")
            raise SystemExit

        except Exception:
            raise

    # -----------------------------
    # config file authentication
    # -----------------------------
    else:
        config = oci.config.from_file(
            oci.config.DEFAULT_LOCATION,
            (config_profile if config_profile else oci.config.DEFAULT_PROFILE)
        )
        signer = oci.signer.Signer(
            tenancy=config["tenancy"],
            user=config["user"],
            fingerprint=config["fingerprint"],
            private_key_file_location=config.get("key_file"),
            pass_phrase=oci.config.get_config_value_or_default(config, "pass_phrase"),
            private_key_content=config.get("key_content")
        )
        return config, signer


##########################################################################
# Configure logging output
##########################################################################
def MakeLog(msg, no_end=False):
    if no_end:
        print(msg, end="")
    else:
        print(msg)


##########################################################################
# isWeekDay
##########################################################################
def isWeekDay(day):
    weekday = True
    if AlternativeWeekend:
        if day == 4 or day == 5:
            weekday = False
    else:
        if day == 5 or day == 6:
            weekday = False
    return weekday


###############################################
# isDeleted
###############################################
def isDeleted(state):
    deleted = False
    try:
        if state == "TERMINATED" or state == "TERMINATING":
            deleted = True
        if state == "DELETED" or state == "DELETING":
            deleted = True
    except Exception:
        deleted = True
        MakeLog("No lifecyclestate found, ignoring resource")
        MakeLog(state)

    return deleted


###############################################
# AutonomousThread
###############################################
class AutonomousThread(threading.Thread):

    def __init__(self, threadID, ID, NAME, CPU):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ID = ID
        self.NAME = NAME
        self.CPU = CPU

    def run(self):
        global total_resources
        global ErrorsFound
        global errors
        global success

        MakeLog(" - Starting Autonomous DB {} and after that scaling to {} cpus".format(self.NAME, self.CPU))
        Retry = True
        while Retry:
            try:
                response = database.start_autonomous_database(autonomous_database_id=self.ID)
                Retry = False
                success.append("Started Autonomous DB {}".format(self.NAME))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    ErrorsFound = True
                    errors.append(" - Error ({}) Starting Autonomous DB {}".format(response.status, self.NAME))
                    Retry = False

        response = database.get_autonomous_database(autonomous_database_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)

        time.sleep(10)
        while response.data.lifecycle_state != "AVAILABLE":
            response = database.get_autonomous_database(autonomous_database_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
            time.sleep(10)
        MakeLog("Autonomous DB {} started, re-scaling to {} cpus".format(self.NAME, self.CPU))
        dbupdate = oci.database.models.UpdateAutonomousDatabaseDetails()
        dbupdate.cpu_core_count = self.CPU

        Retry = True
        while Retry:
            try:
                response = database.update_autonomous_database(autonomous_database_id=self.ID, update_autonomous_database_details=dbupdate)
                Retry = False
                success.append("Autonomous DB {} started, re-scaling to {} cpus".format(self.NAME, self.CPU))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    errors.append(" - Error ({}) re-scaling to {} cpus for {}".format(response.status, self.CPU, self.NAME))
                    Retry = False


###############################################
# PoolThread
###############################################
class PoolThread(threading.Thread):

    def __init__(self, threadID, ID, NAME, INSTANCES):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ID = ID
        self.NAME = NAME
        self.INSTANCES = INSTANCES

    def run(self):
        global total_resources
        global ErrorsFound
        global errors
        global success

        MakeLog(" - Starting Instance Pool {} and after that scaling to {} instances".format(self.NAME, self.INSTANCES))
        Retry = True
        while Retry:
            try:
                response = pool.start_instance_pool(instance_pool_id=self.ID)
                Retry = False
                success.append(" - Starting Instance Pool {}".format(self.NAME))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    errors.append(" - Error ({}) starting instance pool {}".format(response.status, self.NAME))
                    Retry = False

        response = pool.get_instance_pool(instance_pool_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
        time.sleep(10)
        while response.data.lifecycle_state != "RUNNING":
            response = pool.get_instance_pool(instance_pool_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
            time.sleep(10)
        MakeLog("Instance pool {} started, re-scaling to {} instances".format(self.NAME, self.INSTANCES))
        pooldetails = oci.core.models.UpdateInstancePoolDetails()
        pooldetails.size = self.INSTANCES

        Retry = True
        while Retry:
            try:
                response = pool.update_instance_pool(instance_pool_id=self.ID, update_instance_pool_details=pooldetails)
                Retry = False
                success.append("Rescaling Instance Pool {} to {} instances".format(self.NAME, self.INSTANCES))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    ErrorsFound = True
                    errors.append(" - Error ({}) rescaling instance pool {}".format(response.status, self.NAME))
                    Retry = False


###############################################
# AnalyticsThread
###############################################
class AnalyticsThread(threading.Thread):

    def __init__(self, threadID, ID, NAME, CPU):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ID = ID
        self.NAME = NAME
        self.CPU = CPU

    def run(self):
        global total_resources
        global ErrorsFound
        global errors
        global success

        MakeLog(" - Starting Analytics Service {} and after that scaling to {} cpus".format(self.NAME, self.CPU))
        Retry = True
        while Retry:
            try:
                response = analytics.start_analytics_instance(analytics_instance_id=self.ID)
                Retry = False
                success.append("Started Analytics Service {}".format(self.NAME))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    ErrorsFound = True
                    errors.append(" - Error ({}) Starting Analytics Service {}".format(response.status, self.NAME))
                    Retry = False

        response = analytics.get_analytics_instance(analytics_instance_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
        time.sleep(10)
        while response.data.lifecycle_state != "ACTIVE":
            response = analytics.get_analytics_instance(analytics_instance_id=self.ID, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
            time.sleep(10)
        MakeLog("Analytics Service {} started, re-scaling to {} cpus".format(self.NAME, self.CPU))
        capacity = oci.analytics.models.capacity.Capacity()
        capacity.capacity_value = self.CPU
        capacity.capacity_type = capacity.CAPACITY_TYPE_OLPU_COUNT
        details = oci.analytics.models.ScaleAnalyticsInstanceDetails()
        details.capacity = capacity
        Retry = True
        while Retry:
            try:
                response = analytics.scale_analytics_instance(analytics_instance_id=self.ID, scale_analytics_instance_details=details)
                Retry = False
                success.append("Analytics Service {} started, re-scaling to {} cpus".format(self.NAME, self.CPU))
            except oci.exceptions.ServiceError as response:
                if response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    errors.append("Error ({}) re-scaling Analytics to {} cpus for {}".format(response.status, self.CPU, self.NAME))
                    Retry = False


##########################################################################
# Load compartments
##########################################################################
def identity_read_compartments(identity, tenancy):

    MakeLog("Loading Compartments...")
    try:
        cs = oci.pagination.list_call_get_all_results(
            identity.list_compartments,
            tenancy.id,
            compartment_id_in_subtree=True,
            retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
        ).data

        # Add root compartment which is not part of the list_compartments
        tenant_compartment = oci.identity.models.Compartment()
        tenant_compartment.id = tenancy.id
        tenant_compartment.name = tenancy.name
        tenant_compartment.lifecycle_state = oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE
        cs.append(tenant_compartment)

        MakeLog("    Total " + str(len(cs)) + " compartments loaded.")
        return cs

    except Exception as e:
        raise RuntimeError("Error in identity_read_compartments: " + str(e.args))


##########################################################################
# Handle Region
##########################################################################
def autoscale_region(region):

    # Global Paramters for update
    global total_resources
    global ErrorsFound
    global errors
    global success

    MakeLog("Starting Auto Scaling script on region {}, executing {} actions".format(region, Action))

    threads = []  # Thread array for async AutonomousDB start and rescale
    tcount = 0

    ###############################################
    # Get Current Day, time
    ###############################################
    DayOfWeek, Day, CurrentHour = get_current_hour(region, cmd.ignore_region_time)

    if AlternativeWeekend:
        MakeLog("Using Alternative weekend (Friday and Saturday as weekend")
    if cmd.ignore_region_time:
        MakeLog("Ignoring Region Datetime, Using local time")

    MakeLog("Day of week: {}, IsWeekday: {},  Current hour: {}".format(Day, isWeekDay(DayOfWeek), CurrentHour))

    # Array start with 0 so decrease CurrentHour with 1, if hour = 0 then 23
    CurrentHour = 23 if CurrentHour == 0 else CurrentHour - 1

    ###############################################
    # Find all resources with a Schedule Tag
    ###############################################
    MakeLog("Getting all resources supported by the search function...")
    query = "query all resources where (definedTags.namespace = '{}')".format(PredefinedTag)
    query += " && compartmentId  = '" + compartment_include + "'" if compartment_include else ""
    query += " && compartmentId != '" + compartment_exclude + "'" if compartment_exclude else ""
    sdetails = oci.resource_search.models.StructuredSearchDetails()
    sdetails.query = query
    result = search.search_resources(search_details=sdetails, limit=1000, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data

    #################################################################
    # Find additional resources not found by search (MySQL Service)
    #################################################################
    if not cmd.ignoremysql:

        MakeLog("Finding MySQL instances in {} Compartments...".format(len(compartments)))
        for c in compartments:

            # check compartment include and exclude
            if c.lifecycle_state != oci.identity.models.Compartment.LIFECYCLE_STATE_ACTIVE:
                continue
            if compartment_include:
                if c.id != compartment_include:
                    continue
            if compartment_exclude:
                if c.id == compartment_exclude:
                    continue

            mysql_instances = []
            try:
                mysql_instances = oci.pagination.list_call_get_all_results(
                    mysql.list_db_systems,
                    compartment_id=c.id,
                    retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
                ).data
            except Exception:
                MakeLog("e", True)
                continue

            MakeLog(".", True)

            for mysql_instance in mysql_instances:
                if PredefinedTag not in mysql_instance.defined_tags or mysql_instance.lifecycle_state != "ACTIVE":
                    continue

                summary = oci.resource_search.models.ResourceSummary()
                summary.availability_domain = mysql_instance.availability_domain
                summary.compartment_id = mysql_instance.compartment_id
                summary.defined_tags = mysql_instance.defined_tags
                summary.freeform_tags = mysql_instance.freeform_tags
                summary.identifier = mysql_instance.id
                summary.lifecycle_state = mysql_instance.lifecycle_state
                summary.display_name = mysql_instance.display_name
                summary.resource_type = "MysqlDBInstance"
                result.items.append(summary)

        MakeLog("")

    #################################################################
    # All the items with a schedule are now collected.
    # Let's go thru them and find / validate the correct schedule
    #################################################################
    total_resources += len(result.items)

    MakeLog("")
    MakeLog("Checking {} Resources for Auto Scale...".format(len(result.items)))
    MakeLog("#########################################################")

    for resource in result.items:
        # The search data is not always updated. Get the tags from the actual resource itself, not using the search data.
        resourceOk = False
        if cmd.print_ocid:
            MakeLog("Checking {} ({}) - {}...".format(resource.display_name, resource.resource_type, resource.identifier))
        else:
            MakeLog("Checking {} ({})...".format(resource.display_name, resource.resource_type))

        if resource.resource_type == "Instance":
            resourceDetails = compute.get_instance(instance_id=resource.identifier, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
            resourceOk = True
        if not isDeleted(resource.lifecycle_state) and resourceOk:
            schedule = resourceDetails.defined_tags[PredefinedTag]
            ActiveSchedule = ""

            if AnyDay in schedule:
                ActiveSchedule = schedule[AnyDay]
            if isWeekDay(DayOfWeek):  # check for weekday / weekend
                if WeekDay in schedule:
                    ActiveSchedule = schedule[WeekDay]
            else:
                if Weekend in schedule:
                    ActiveSchedule = schedule[Weekend]

            if Day in schedule:  # Check for day specific tag (today)
                ActiveSchedule = schedule[Day]
            ###################################################################################
            # Instance
            ###################################################################################
            if ActiveSchedule != "":
                if resourceDetails.shape[:2] == "VM":
                    try:
                        times = ActiveSchedule.split(";")
                        date_time = datetime.datetime.now()
                        time = date_time.time()
                        current_time = date_time.strftime("%H:%M")
                        print('Present time - >', current_time)
                        for window in [time for time in times if time]:
                            start, stop = window.split("-")[0], window.split("-")[1]
                            if current_time >= start and current_time <= stop:
                                print(current_time + " - is in range of -> " + window)
                                if resourceDetails.lifecycle_state == "STOPPED" and time.strftime("%H:%M") == start:
                                    print("- starting instance.....{}".format(resource.display_name))
                                    response = compute.instance_action(instance_id=resource.identifier, action="START")
                                    print(response)
                                if resourceDetails.lifecycle_state == "RUNNING" and time.strftime("%H:%M") == stop:
                                    MakeLog(" - stopping the instace.....{}".format(resource.display_name))
                                    response = compute.instance_action(instance_id=resource.identifier, action=ComputeShutdownMethod) # STOP
                                    print(response)
                                break
                            else:
                                print(current_time + "- is not in range of -> " + window)
                                continue
                        print("checking done for the instance.....{}".format(resource.display_name))
                        print("#########################################################")
                    except Exception:
                        ErrorsFound = True
                        ActiveSchedule = ""
                        errors.append(" - Error with schedule for {}".format(resource.display_name))
                        MakeLog(" - Error with schedule of {}".format(resource.display_name))
                        MakeLog(sys.exc_info()[0])
            else:
                MakeLog(" - Ignoring instance, as no active schedule for today found")
    ###################################################################################
    # Wait for any AutonomousDB and Instance Pool Start and rescale tasks completed
    ###################################################################################
    MakeLog("Waiting for all threads to complete...")
    for t in threads:
        t.join()
    MakeLog("Region {} Completed.".format(region))

##########################################################################
# Main
##########################################################################
# Get Command Line Parser
parser = argparse.ArgumentParser()
parser.add_argument('-t', default="", dest='config_profile', help='Config file section to use (tenancy profile)')
parser.add_argument('-ip', action='store_true', default=False, dest='is_instance_principals', help='Use Instance Principals for Authentication')
parser.add_argument('-dt', action='store_true', default=False, dest='is_delegation_token', help='Use Delegation Token for Authentication')
parser.add_argument('-a', default="All", dest='action', help='Action All, Down, Up')
parser.add_argument('-tag', default="Schedule", dest='tag', help='Tag to examine, Default=Schedule')
parser.add_argument('-rg', default="", dest='filter_region', help='Filter Region')
parser.add_argument('-ic', default="", dest='compartment_include', help='Include Compartment OCID')
parser.add_argument('-ec', default="", dest='compartment_exclude', help='Exclude Compartment OCID')
parser.add_argument('-ignrtime', action='store_true', default=False, dest='ignore_region_time', help='Ignore Region Time - Use Host Time')
parser.add_argument('-ignoremysql', action='store_true', default=False, dest='ignoremysql', help='Ignore MYSQL processing')
parser.add_argument('-printocid', action='store_true', default=False, dest='print_ocid', help='Print OCID for resources')
parser.add_argument('-topic', default="", dest='topic', help='Topic to send summary in home region')

cmd = parser.parse_args()
if cmd.action != "All" and cmd.action != "Down" and cmd.action != "Up":
    parser.print_help()
    sys.exit(0)

####################################
# Assign variables
####################################
filter_region = cmd.filter_region
Action = cmd.action
PredefinedTag = cmd.tag
compartment_exclude = cmd.compartment_exclude if cmd.compartment_exclude else ""
compartment_include = cmd.compartment_include if cmd.compartment_include else ""

####################################
# Start print time info
####################################
start_time = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print_header("Running Auto Scale")

# Identity extract compartments
config, signer = create_signer(cmd.config_profile, cmd.is_instance_principals, cmd.is_delegation_token)
compartments = []
tenancy = None
tenancy_home_region = ""

try:
    MakeLog("Starts at " + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    MakeLog("\nConnecting to Identity Service...")
    identity = oci.identity.IdentityClient(config, signer=signer)
    tenancy = identity.get_tenancy(config["tenancy"]).data
    regions = identity.list_region_subscriptions(tenancy.id).data

    for reg in regions:
        if reg.is_home_region:
            tenancy_home_region = str(reg.region_name)

    MakeLog("")
    MakeLog("Version       : " + str(Version))
    MakeLog("Command Line  : " + ' '.join(x for x in sys.argv[1:]))
    MakeLog("Tenant Name   : " + str(tenancy.name))
    MakeLog("Tenant Id     : " + tenancy.id)
    MakeLog("Home Region   : " + tenancy_home_region)
    MakeLog("Action        : " + Action)
    MakeLog("Tag           : " + PredefinedTag)

    if cmd.topic:
        MakeLog("Topic         : " + cmd.topic)
    if cmd.filter_region:
        MakeLog("Filter Region : " + cmd.filter_region)

    MakeLog("")
    compartments = identity_read_compartments(identity, tenancy)

except Exception as e:
    raise RuntimeError("\nError connecting to Identity Service - " + str(e))

############################################
# Define Global Variables to store info
############################################
success = []
errors = []
total_resources = 0
ErrorsFound = False

############################################
# Loop on all regions
############################################
#for region_name in [str(es.region_name) for es in regions]:

#    if cmd.filter_region:
#        if cmd.filter_region not in region_name:
#            continue

#    print_header("Region " + region_name)

    # set the region in the config and signer
#    config['region'] = region_name
#    signer.region = region_name

    ###############################################
    # services - global used by threads as well
    ###############################################
#    compute = oci.core.ComputeClient(config, signer=signer)
#    database = oci.database.DatabaseClient(config, signer=signer)
#    pool = oci.core.ComputeManagementClient(config, signer=signer)
#    search = oci.resource_search.ResourceSearchClient(config, signer=signer)
#    oda = oci.oda.OdaClient(config, signer=signer)
#    analytics = oci.analytics.AnalyticsClient(config, signer=signer)
#    integration = oci.integration.IntegrationInstanceClient(config, signer=signer)
#    loadbalancer = oci.load_balancer.LoadBalancerClient(config, signer=signer)
#    mysql = oci.mysql.DbSystemClient(config, signer=signer)
#    goldengate = oci.golden_gate.GoldenGateClient(config, signer=signer)
#    dataintegration = oci.data_integration.DataIntegrationClient(config, signer=signer)

    ###############################################
    # Run Scale Region
    ###############################################
#    print_header("Region " + "eu-frankfurt-1")
#    MakeLog("region name .... " + "eu-frankfurt-1")
#    autoscale_region("eu-frankfurt-1")
#   # autoscale_region(region_name)
compute = oci.core.ComputeClient(config, signer=signer)
database = oci.database.DatabaseClient(config, signer=signer)
pool = oci.core.ComputeManagementClient(config, signer=signer)
search = oci.resource_search.ResourceSearchClient(config, signer=signer)
oda = oci.oda.OdaClient(config, signer=signer)
analytics = oci.analytics.AnalyticsClient(config, signer=signer)
integration = oci.integration.IntegrationInstanceClient(config, signer=signer)
loadbalancer = oci.load_balancer.LoadBalancerClient(config, signer=signer)
mysql = oci.mysql.DbSystemClient(config, signer=signer)
goldengate = oci.golden_gate.GoldenGateClient(config, signer=signer)
dataintegration = oci.data_integration.DataIntegrationClient(config, signer=signer)
###############################################
# Run Scale Region
###############################################
MakeLog("Home region ..."+ tenancy_home_region)
autoscale_region(tenancy_home_region)

############################################
# Send summary if Topic Specified
############################################
if cmd.topic:

    # set the home region in the config and signer
    config['region'] = tenancy_home_region
    signer.region = tenancy_home_region

    ns = oci.ons.NotificationDataPlaneClient(config, signer=signer)

    if LogLevel == "ALL" or (LogLevel == "ERRORS" and ErrorsFound):
        MakeLog("\nPublishing notification")
        body_message = "Scaling ({}) just completed. Found {} errors across {} scaleable instances (from a total of {} instances). \nError Details: {}\n\nSuccess Details: {}".format(Action, len(errors), len(success), total_resources, errors, success)
        Retry = True

        while Retry:
            try:
                ns_response = ns.publish_message(cmd.topic, {"title": "Scaling Script ran across tenancy: {}".format(tenancy.name), "body": body_message})
                Retry = False
            except oci.exceptions.ServiceError as ns_response:
                if ns_response.status == 429:
                    MakeLog("Rate limit kicking in.. waiting {} seconds...".format(RateLimitDelay))
                    time.sleep(RateLimitDelay)
                else:
                    MakeLog("Error ({}) publishing notification - {}".format(ns_response.status, ns_response.message))
                    Retry = False

MakeLog("All scaling tasks done, checked {} resources.".format(total_resources))
