"""
FindResource
------------
Retrieve a resource ID from AWS for use in a CloudFormation Stack
"""

from aws_helpers import AWSClient, getLambdaEnv, configLogging
import json
import operator
import re
from botocore.vendored import requests
from botocore.config import Config

# INIT
LOGGING_LEVEL = None
AWS = None
LOGGER = None

class Finder:
	def __init__(self):
		self.AWS = AWSClient()
		pass

	def get_az_for_subnet(self, subnetArg):
		'''
		Give str(subnetId)
		Return str(AZName)
		'''
		az = None
		subnets = self.AWS.get_simple(REGION, 'ec2', 'describe_subnets', 'Subnets')
		for subnet in subnets:
			if subnet['SubnetId'] == subnetArg:
				az = subnet['AvailabilityZone']
		return az

	def get_ami(self, props):
		'''
		Given queryprops, return the newest matching AMI Id
		'''
		archToAMINamePattern = {
			'PV64-EBS': 'amzn-ami-pv*-x86_64-ebs',
			'HVM64-GP2': 'amzn-ami-hvm*.x86_64-gp2',
			'HVM64-2-GP2': 'amzn2-ami-hvm-2.0.*-x86_64-gp2',
			'HVMG2-EBS': 'amzn-ami-graphics-hvm-*x86_64-ebs*',
		}

		if 'Architecture' not in props:
			return {'Error': 'Architecture not in QueryProps'}
		if props['Architecture'] not in archToAMINamePattern:
			return {'Error': 'Unrecognized Architecture. Select one of ' + json.dumps(archToAMINamePattern)}

		filters = {
			"Filters": [
				{
					"Name": "name",
					"Values": [ archToAMINamePattern[props['Architecture']] ]
				}
			]
		}

		amiidlist = self.AWS.get_simple(REGION, 'ec2', 'describe_images', 'Images', filters)

		amiid = None
		newest = ''
		if amiidlist:
			for ami in amiidlist:
				# Ignore release candidates
				if re.match('.*-rc-.*', ami['Name']):
					LOGGER.debug('Ignore RC ' + ami['Name'])
					continue
				if ami['Name'] > newest:
					newest = ami['Name']
					LOGGER.debug('newest is now ' + ami['Name'])
					amiid = ami['ImageId']
		
		return amiid

def send_response(event, context, status, data=None):

	response_url = None

	if 'ResponseURL' in event:
		response_url = event['ResponseURL']
	else:
		LOGGER.warning('Request did not contain a ResponseURL.')
		if data:
			LOGGER.info(data)
		return 500

	response_body = {}
	response_body['Status'] = status
	response_body['Reason'] = 'Log Stream=%s' % context.log_stream_name
	response_body['PhysicalResourceId'] = context.log_stream_name
	response_body['StackId'] = event['StackId'] if 'StackId' in event else "Unknown StackId"
	response_body['RequestId'] = event['RequestId'] if 'RequestId' in event else "Unknown RequestId"
	response_body['LogicalResourceId'] = (event['LogicalResourceId'] if 'LogicalResourceId' in event
										  else "Unknown LogicalResourceId")

	response_body['Data'] = data if data else {}
	json_body = json.dumps(response_body)
	LOGGER.debug("Response %s" % json_body)
	headers = {
		'content-type': '',
		'content-length': str(len(json_body))
	}

	try:
		response = requests.put(response_url, data=json_body, headers=headers)

	except Exception as e:
		LOGGER.error("Failed to send response. stack-id=%(stack)s, resource-type=%(rt)s, err=%(err)s, url=%(url)s" %
				{
					'stack': event['StackId'],
					'rt': event['ResourceType'],
					'err': e,
					'url': response_url
				})
		return 500

	else:
		LOGGER.info("Response sent, status=%(code)s, url=%(url)s" %
				{'code': response.reason, 'url': response_url})
		return response.reason

def lambda_handler(event, context):

	responseData = {}
	status = 'FAILED'
	

	print(json.dumps(event, indent=2))

	if 'RequestType' not in event:
		event['RequestType'] = 'search'

	#
	# for update run the query and return a result. For delete and create just return success
	#
	if event['RequestType'].lower() == 'delete':
		send_response(event, context, 'SUCCESS')
		return
	# if event['RequestType'].lower() == 'create':
	# 	send_response(event, context, 'SUCCESS')
	# 	return


	if 'ResourceProperties' in event and \
	   'Query' in event['ResourceProperties'] and 'QueryProps' in event['ResourceProperties']:
		# Alias the dicts for simplicity
		resProps = event['ResourceProperties']
		queryProps = resProps['QueryProps']

		if resProps['Query'] == 'GetAZforSubnet':
			response = AWSFinder.get_az_for_subnet(queryProps['subnetid'])
			if response:
				responseData = { 'AZ': response }

		elif resProps['Query'] == 'GetAMI':
			if 'Architecture' not in queryProps:
				responseData = {'Error': 'Missing QueryProps[\'Architecture\']'}
			else:
				response = AWSFinder.get_ami(queryProps)
				if response:
					responseData = { 'AMIId': response }
		else:
			responseData = {'Error': 'unrecognized query ' + json.dumps(event)}
	else: 
		responseData = {'Error': 'Invalid request: missing Query'}

	if responseData and 'Error' not in responseData:
		status = 'SUCCESS'
	else:
		LOGGER.warning(responseData['Error'])

	send_response(event, context, status, responseData)
	return responseData

LOGGING_LEVEL = getLambdaEnv('LOGGING_LEVEL', 'INFO').upper()
if LOGGING_LEVEL not in ('INFO', 'DEBUG', 'ERROR', 'WARNING'):
	LOGGING_LEVEL = 'DEBUG'
	print('Error: LOGGING_LEVEL defaulted to DEBUG')

LOGGER = configLogging(LOGGER, LOGGING_LEVEL)
REGION = getLambdaEnv('AWS_DEFAULT_REGION')
AWSFinder = Finder()
