#!/usr/bin/python

import boto3

CloudVar  = {}
CloudVar['REGION_NAME']               = "eu-west-1"
CloudVar['AVZ1']                      = "eu-west-1a"
CloudVar['AVZ2']                      = "eu-west-1b"
CloudVar['CIDRange']                  = "10.15.0.0/23"

CloudVar['avz1_pvtsubnet_CIDRange']   = "10.15.0.0/25"
CloudVar['avz1_pubsubnet_CIDRange']   = "10.15.0.128/26"

CloudVar['avz2_pvtsubnet_CIDRange']   = "10.15.1.0/25"
CloudVar['avz2_pubsubnet_CIDRange']   = "10.15.1.128/26"

CloudVar['Project']                  = { 'Key':'Name', 'Value':'InternedServices'}
CloudVar['tags']                     = [{'Key':'Owner', 'Value':'Devesh'},
                                          {'Key':'Environment', 'Value':'DEV'}]
# CloudVar['EC2-KeyName']              = CloudVar['Project']['Value']+'-Key'

# Creating a VPC, Subnet, and Gateway
ec2         = boto3.resource ( 'ec2', region_name = CloudVar['REGION_NAME'] )
ec2Client   = boto3.client   ( 'ec2', region_name = CloudVar['REGION_NAME'] )
vpc         = ec2.create_vpc ( CidrBlock = CloudVar['CIDRange'] )

# AVZ1 Subnets
avz1_pvtsubnet   = vpc.create_subnet( CidrBlock = CloudVar['avz1_pvtsubnet_CIDRange'], AvailabilityZone = CloudVar['AVZ1'] )
avz1_pubsubnet   = vpc.create_subnet( CidrBlock = CloudVar['avz1_pubsubnet_CIDRange'], AvailabilityZone = CloudVar['AVZ1'] )

# AVZ2 Subnet
avz2_pvtsubnet   = vpc.create_subnet( CidrBlock = CloudVar['avz2_pvtsubnet_CIDRange'], AvailabilityZone = CloudVar['AVZ2'] )
avz2_pubsubnet   = vpc.create_subnet( CidrBlock = CloudVar['avz2_pubsubnet_CIDRange'], AvailabilityZone = CloudVar['AVZ2'] )

# Enable DNS Hostnames in the VPC
vpc.modify_attribute( EnableDnsSupport 		= { 'Value': True } )
vpc.modify_attribute( EnableDnsHostnames 	= { 'Value': True } )

# Create the Internet Gatway & Attach to the VPC
intGateway  = ec2.create_internet_gateway()
intGateway.attach_to_vpc( VpcId = vpc.id )

# Create another route table for Public traffic
pubRouteTable = ec2.create_route_table( VpcId = vpc.id )
pubRouteTable.associate_with_subnet( SubnetId = avz1_pubsubnet.id )
pubRouteTable.associate_with_subnet( SubnetId = avz2_pubsubnet.id )

# Create another route table for Private traffic
pvtRouteTable = ec2.create_route_table( VpcId = vpc.id )
pvtRouteTable.associate_with_subnet( SubnetId = avz1_pvtsubnet.id )
pvtRouteTable.associate_with_subnet( SubnetId = avz2_pvtsubnet.id )

# Create a route for internet traffic to flow out
intRoute = ec2Client.create_route( RouteTableId = pubRouteTable.id , DestinationCidrBlock = '0.0.0.0/0' , GatewayId = intGateway.id )

# Tag the resources
vpc.create_tags                ( Tags = CloudVar['tags'] )
avz1_pvtsubnet.create_tags     ( Tags = CloudVar['tags'] )
avz1_pubsubnet.create_tags     ( Tags = CloudVar['tags'] )
avz2_pvtsubnet.create_tags     ( Tags = CloudVar['tags'] )
avz2_pubsubnet.create_tags     ( Tags = CloudVar['tags'] )
intGateway.create_tags         ( Tags = CloudVar['tags'] )
pubRouteTable.create_tags      ( Tags = CloudVar['tags'] )
pvtRouteTable.create_tags      ( Tags = CloudVar['tags'] )

vpc.create_tags                ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-vpc'}] )
avz1_pvtsubnet.create_tags     ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-avz1-private-subnet'}] )
avz1_pubsubnet.create_tags     ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-avz1-public-subnet'}] )
avz2_pvtsubnet.create_tags     ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-avz2-private-subnet'}] )
avz2_pubsubnet.create_tags     ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-avz2-public-subnet'}] )
intGateway.create_tags         ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-igw'}] )
pubRouteTable.create_tags      ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-rtb'}] )
pvtRouteTable.create_tags      ( Tags = [{'Key':'Name', 'Value':CloudVar['Project']['Value']+'-rtb'}] )

# Let create the Public & Private Security Groups
pubSecGrp = ec2.create_security_group( 
	DryRun = False, 
	GroupName='pubSecGrp',
	Description='Public_Security_Group',
	VpcId= vpc.id
)

pvtSecGrp = ec2.create_security_group( 
	DryRun = False, 
	GroupName='pvtSecGrp',
	Description='Private_Security_Group',
	VpcId= vpc.id
)


pubSecGrp.create_tags( Tags = CloudVar['tags'] )
pvtSecGrp.create_tags( Tags = CloudVar['tags'] )

pubSecGrp.create_tags(Tags=[{'Key': 'Name' ,'Value': CloudVar['Project']['Value']+'-public-security-group'}])
pvtSecGrp.create_tags(Tags=[{'Key': 'Name' ,'Value': CloudVar['Project']['Value']+'-private-security-group'}])

# Allow Public Security Group to receive traffic from ELB Security group
ec2Client.authorize_security_group_ingress( 
	GroupId = pubSecGrp.id,
	IpPermissions = [{
    	'IpProtocol': 'tcp',
		'FromPort': 80,
		'ToPort': 80,
	}]
)
# Allow Private Security Group to receive traffic from Application Security group
ec2Client.authorize_security_group_ingress( 
	GroupId = pvtSecGrp.id,
	IpPermissions = [{
    	'IpProtocol': 'tcp',
		'FromPort': 80,
		'ToPort': 80,
		'UserIdGroupPairs': [{ 'GroupId':pubSecGrp.id}]
	}]
)

ec2Client.authorize_security_group_ingress( 
	GroupId  = pubSecGrp.id ,
	IpProtocol= 'tcp',
	FromPort=80,
	ToPort=80,
	CidrIp='0.0.0.0/0'
)
ec2Client.authorize_security_group_ingress( 
	GroupId  = pubSecGrp.id ,
	IpProtocol= 'tcp',
    FromPort=443,
	ToPort=443,
	CidrIp='0.0.0.0/0'
)
ec2Client.authorize_security_group_ingress( 
	GroupId  = pubSecGrp.id ,
	IpProtocol= 'tcp',
	FromPort=22,
	ToPort=22,
	CidrIp='0.0.0.0/0'
)
ec2Client.authorize_security_group_ingress( 
	GroupId  = pubSecGrp.id ,
	IpProtocol= 'tcp',
	FromPort=3389,
	ToPort=3389,
	CidrIp='0.0.0.0/0'
)
ec2Client.authorize_security_group_ingress( 
	GroupId  = pubSecGrp.id ,
	IpProtocol= 'tcp',
	FromPort=0,
	ToPort=65535,
	CidrIp='0.0.0.0/0'
)
ec2Client.authorize_security_group_ingress( 
	GroupId  = pvtSecGrp.id ,
	IpProtocol= 'tcp',
	FromPort=3389,
	ToPort=3389,
	CidrIp='10.82.0.0/16'
)
