"""
FindResource
------------
Retrieve a resource ID from AWS for use in a CloudFormation Stack
"""

from aws_helpers import AWSClient, getLambdaEnv, configLogging
import json
import operator
import re

# INIT
LOGGING_LEVEL = None
AWS = None
LOGGER = None
def get_az_for_subnet(subnetArg):
	'''
	Give str(subnetId)
	Return str(AZName)
	'''
	az = None
	subnets = AWS.get_simple(REGION, 'ec2', 'describe_subnets', 'Subnets')
	for subnet in subnets:
		if subnet['SubnetId'] == subnetArg:
			az = subnet['AvailabilityZone']
	return az

def get_ami(props):
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

	amiidlist = AWS.get_simple(REGION, 'ec2', 'describe_images', 'Images', filters)

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

	if 'ResponseUrl' in event:
		response_url = event['ResponseURL']
	else:
		LOGGER.warning('Request did not contain a ResponseUrl.')
		LOGGER.info(json.dumps(data, indent=2))
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
		response = requests.put(response_url, data=json_body, headers=headers, proxies=PROXIES)

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
		LOG.info("Response sent, status=%(code)s, url=%(url)s" %
				{'code': response.reason, 'url': response_url})
		return response.reason

def lambda_handler(event, context):

	responseData = {}
	status = 'FAILED'

	if 'RequestType' not in event:
		event['RequestType'] = 'search'

	# for update and create events run the query and return a result. For delete just return success
	if event['RequestType'].lower() == 'delete':
		send_response(event, context, SUCCESS)
		return

	if 'ResourceProperties' not in event or \
	   'Query' not in event['ResourceProperties']:
		responseData = {'Error': 'Invalid request: missing Query'}
	else:
		# Alias the dicts for simplicity
		resProps = event['ResourceProperties']
		queryProps = resProps['QueryProps']

		if resProps['Query'] == 'GetAZforSubnet':
			responseData = get_az_for_subnet(queryProps['subnetid'])

		elif resProps['Query'] == 'GetAMI':
			if 'Architecture' not in queryProps:
				responseData = {'Error': 'Missing QueryProps[\'Architecture\']'}
			else:
				responseData = get_ami(queryProps)
		else:
			responseData = {'Error': 'unrecognized query ' + json.dumps(event)}

	if responseData and 'Error' not in responseData:
		status = 'Success'
	else:
		LOGGER.warning(responseData['Error'])

	send_response(event, context, status, responseData)
	return responseData

LOGGING_LEVEL = getLambdaEnv('LOGGING_LEVEL', 'INFO').upper()
if LOGGING_LEVEL not in ('INFO', 'DEBUG', 'ERROR', 'WARNING'):
	LOGGING_LEVEL = 'DEBUG'
	print('Error: LOGGING_LEVEL defaulted to DEBUG')

LOGGER = configLogging(LOGGER, LOGGING_LEVEL)

AWS = AWSClient()

REGION = getLambdaEnv('AWS_DEFAULT_REGION')
