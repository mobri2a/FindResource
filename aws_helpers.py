"""Helper class for AWS API access"""
#!/usr/bin/python
#***************************************************************************
# Authors/Maintainers:  Mike O'Brien (miobrien@amazon.com)
#
# Description: Helper class for retrieving data from AWS API
#---------------------------------------------------------------------------
# Notes
#---------------------------------------------------------------------------
# To Do List:
# -----------
# - no known issues
#***************************************************************************

# *******************************************************************
# Required Modules:
# *******************************************************************
import boto3
from botocore.exceptions import ClientError
import json

CLIENT = {}
session = ''

class AWSClient:

    profile = ''
    region = ''
    session = None

    def __init__(self, profile):
        session = boto3.session.Session(profile_name=profile)
        boto3.setup_default_session(profile_name=profile)

    def connect(self, service, region):
        """
        Connect to AWS api with connection caching
        Returns: connection handle
        """
        if service in CLIENT and region in CLIENT[service]:
            return CLIENT[service][region]

        if service not in CLIENT:
            CLIENT[service] = {}

        try:
            CLIENT[service][region] = boto3.client(service, region_name=region)
        except Exception as exc:
            print(exc)
            print(f'Could not connect to {service} in region {region}')
            raise
        else:
            return CLIENT[service][region]

    def whoami(self, region='us-east-1'):
        """
        get local account info
        """
        conn = self.connect('sts', region)
        retstuff = conn.get_caller_identity()
        return retstuff

    def get_tokenized(self, region, service, apimethod, responsekey, tokenparm='NextToken', maxname='MaxResults', tokenname='NextToken'):
        """
        Need to figure out how to interpolate the method (api name)
        Intent is to place the numerous times this code appears
        """

        conn = self.connect(service, region)
        token = 'start'
        result = []

        while token:

            if token == 'start': # needed a value to start the loop. Now reset it
                token = ''

            kwargs = {}

            if token:
                kwargs = { tokenparm: token, maxname: 100 }
            else:
                kwargs = { maxname: 100 }

            response = getattr(conn,apimethod)(
                **kwargs
            )

            if tokenname in response:
                token = response[tokenname]
            else:
                token = ''

            result = result + response[responsekey]

        return result

    def get_simple(self, region, service, apimethod, responsekey):
        """
        Simple query-capture-return
        """
        conn = self.connect(service, region)
        response = getattr(conn,apimethod)()

        return response[responsekey]

    #======================================================================
    # get_vpcs
    #======================================================================
    def get_vpcs (self, region):
        """
        Input: str(region)
        Returns: list of vpcs
        """
        return self.get_tokenized(
            region,
            'ec2',
            'describe_vpcs',
            'Vpcs'
        )

    #======================================================================
    # get_sgs
    #======================================================================
    def get_sgs (self, region):
        """
        Input: str(region)
        Returns: list of SecurityGroups
        get_aws_securitygroups: get the data for all sgs in the account in this region
        """
        return self.get_tokenized(
            region,
            'ec2',
            'describe_security_groups',
            'SecurityGroups'
        )

    #======================================================================
    # sg_exists
    #======================================================================
    def sg_exists (self, region, sg):
        """
        Input: str(region), str(sg)
        Returns: boolen
        """
        conn = self.connect('ec2', region)
 
        response = conn.describe_security_groups(
            Filters=[
                {
                    'Name' : 'group-name',
                    'Values' : [sg]
                },
            ],
        )['SecurityGroups']

        return bool(len(response))

    def flow_logs_enabled (self, region, vpc):
        """
        Input: region, vpc id
        Returns: bool
        """
        return bool(len(self.get_tokenized(
            region,
            'ec2',
            'describe_flow_logs',
            'FlowLogs'
        )))

    def get_vpc_endpoints (self, region, vpc):
        """
        Input: region, vpc id
        Returns: list of endpoints
        """
        return self.get_tokenized(
            region,
            'ec2',
            'describe_vpc_endpoints',
            'VpcEndpoints'
        )

    def get_vpc_peerings (self, region):
        """
        Input: region
        Returns: list of active peering connections
        """

        conn = self.connect('ec2', region)

        response = conn.describe_vpc_peering_connections(
            Filters=[
                {
                    'Name': 'status-code',
                    'Values' : ['active']
                }
            ]
        )['VpcPeeringConnections']

        return response

    def get_dhcp_options(self, region, dhcpoptionsid):
        """
        Input: region, dhcpoptionsid
        Returns: json response
        """
        conn = self.connect('ec2', region)

        response = conn.describe_dhcp_options(
            DhcpOptionsIds=[
                dhcpoptionsid,
            ]
        )['DhcpOptions']

        return response

    def get_route_tables(self, region, vpc):
        """
        Get route tables for a vpc
        Returns json
        """
        conn = self.connect('ec2', region)

        response = conn.describe_route_tables(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [vpc]
                }
            ]
        )['RouteTables']

        return response

    def get_subnets (self, region, vpc=False):
        """
        Get all subnets
        Returns json
        """
        conn = self.connect('ec2', region)

        apiargs = {}

        if vpc:
            apiargs['Filters'] = [ { 'Name': 'vpc-id', 'Values': [ vpc ] } ]

        response = conn.describe_subnets(
            **apiargs
        )['Subnets']

        return response

    #======================================================================
    # get_interfaces
    #======================================================================
    def get_interfaces(self, myregion):
        """
        get_interfaces: get the data for all interfaces in the account in this region
        """

        interfaces = []

        conn = self.connect('ec2', myregion)

        response = conn.describe_network_interfaces(
            MaxResults=100,
            Filters=[
                {
                    'Name': 'description',
                    'Values': [
                        'ELB *'
                    ]
                }
            ]
        )

        interfaces = interfaces + response['NetworkInterfaces']

        while 'NextToken' in response:
            response = conn.describe_network_interfaces(
                NextToken=response['NextToken'],
                MaxResults=100,
                Filters=[
                    {
                        'Name': 'description',
                        'Values': [
                            'ELB *'
                        ]
                    }
                ]
            )

            interfaces = interfaces + response['NetworkInterfaces']

        return interfaces

    #======================================================================
    # get_rds
    #======================================================================
    def get_rds(self, region):
        """get the data for all RDS instances in the account in this region"""
        return self.get_tokenized(
            region,
            'rds',
            'describe_db_instances',
            'DBInstances',
            'Marker',
            'MaxRecords',
            'Marker'
        )

    def role_exists(self, rolename):
        """
        Given a role(str)
        Return bool
        """
        conn = self.connect('iam', 'us-east-1')

        try:
            conn.get_role(RoleName=rolename)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                return False
            raise e
        except Exception as e:
            raise e

    #------------------------------------------------------------------
    # lambda_exists
    #------------------------------------------------------------------
    def lambda_exists(self, region, lambdaname):
        """
        Given a lambda(str)
        Return bool
        """
        conn = self.connect('lambda', region)
        try:
            conn.get_function(FunctionName=lambdaname)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return False
            raise e
        except Exception as e:
            raise e

    def support_level (self):
        """
        Return string 'non-paid', 'business', or 'enterprise'
        """
        conn = self.connect('support', 'us-east-1')
        try:
            sevs = conn.describe_severity_levels()['severityLevels']
            if len(sevs) == 5:
                return 'enterprise'
            elif len(sevs) == 4:
                return 'business'
            else:
                return 'non-paid'
        except ClientError as e:
            if e.response['Error']['Code'] == 'SubscriptionRequiredException':
                return 'non-paid'
            raise e
        except Exception as e:
            raise e
        return 'non-paid'

def getLambdaEnv(parmname, defaultval=None):
    """
    Cleanly get the value of a Lambda environmental. Return if found or default
    """
    try:
        myval = os.environ[parmname]
    except Exception as exc:
        if str(exc) == f'\'{parmname}\'':
            myval = defaultval
            print(
                'Environmental variable \'' + parmname +
                '\' not found. Using default [' + str(defaultval) + ']')
        else:
            print(exc)
            print(
                'ERROR: Environmental variable \'' + parmname +
                '\' not found. Exiting')
            raise

    # recast if int or bool
    if isinstance(defaultval, int):
        myval = int(myval)
    elif myval == 'True':
        myval = True
    elif myval == 'False':
        myval = False

    return myval

def configLogging(logLevel):
    
    global log # If already set up don't set it up again
    
    if log!=None:
        return log
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s ::  %(lineno)s ::%(levelname)s :: %(funcName)10s :: %(message)s'))
        log = logging.getLogger('ConfigDiscoveryLogger')
        log.addHandler(stream_handler)
    
        if logLevel=='DEBUG':
            log.setLevel(logging.DEBUG)
        elif logLevel=='INFO':
            log.setLevel(logging.INFO)
        elif logLevel=='WARNING':
            log.setLevel(logging.WARNING)
        elif logLevel=='ERROR':
            log.setLevel(logging.ERROR)
        elif logLevel=='CRITICAL':
            log.setLevel(logging.CRITICAL)
        else:
            log.setLevel(logging.NOTSET)
        
        return log