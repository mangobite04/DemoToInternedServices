# AWS Architecture Setup

There are two parts to the setup,
- **Part 1** - Setting up the network infrastructure (VPC, Subnets, Security Groups)

Assuming you have already setup your AWS CLI for Region `EU West (Ireland)`.

# Part 1 - Create VPC, Subnet, Security Group
### Setting the AWS Region
```sh
export AWS_DEFAULT_REGION=eu-west-1
```

### Creating a VPC
Lets create a `Virtual Private Cloud - VPC` for our setup with /20 range and get our VPC ID using the `query` parameter and set the output format to `text`. Its is a good practice to give meaningful name to the AWS resources, Lets call our VPC `tmpVPC`

```sh
vpcID=$(aws ec2 create-vpc \
      --cidr-block 10.15.0.0/23 \
      --query 'Vpc.VpcId' \
      --output text)
```
##### Tag the VPC
```sh
aws ec2 create-tags --resources "$vpcID" --tags 'Key=Name,Value=tmpVPC'
```

Instances launched inside a VPC are invisible to the rest of the internet by default. AWS therefore does not bother assigning them a public DNS name. This can be changed easily by enabling the `DNS` support as shown below,

```sh
aws ec2 modify-vpc-attribute --vpc-id "$vpcID" --enable-dns-support "{\"Value\":true}"
aws ec2 modify-vpc-attribute --vpc-id "$vpcID" --enable-dns-hostnames "{\"Value\":true}"
```

_Check if internet gateway is set. If it wasn't there then do these,_
```sh 
internetGatewayId=$(aws ec2 create-internet-gateway \
                  --query 'InternetGateway.InternetGatewayId' \
                  --output text) && echo "$internetGatewayId"
aws ec2 attach-internet-gateway --internet-gateway-id "$internetGatewayId" --vpc-id "$vpcID"
```

##### Tag the Internet Gateway

```sh
aws ec2 create-tags --resources $internetGatewayId --tags 'Key=Name,Value=tmpVPC-Internet-Gateway'
```

<sup>I have chosen /23 CIDR deliberately to allow us to create different subnets for our db, web instances and reserve some for the future. You might want to choose something else that works better for you. **Important:** _AWS reserves both the first four and the last IP address in each subnet's CIDR block. They're not available for use. The smallest subnet (and VPC) you can create uses a /28 netmask (16 IP addresses), and the largest uses a /16 netmask (65,536 IP addresses). Excellent resources to understand CIDR blocks [here](http://bradthemad.org/tech/notes/cidr_subnets.php) & [here](https://coderwall.com/p/ndm54w/creating-an-ec2-instance-in-a-vpc-with-the-aws-command-line-interface) & my quick help [gist](https://gist.github.com/miztiik/baecbaa67b1f10e38186d70e51c13a6c#file-cidr-ip-range)_<sup>

## Subnet Reservation for Server's [Database or WebServer]

| VPC Range    | Availability Zone  | Region        | Reservation Purpose | IP Ranges      | IP Range        |
|--------------|--------------------|---------------|---------------------|----------------|-----------------|
| 10.15.0.0/23 |                    |               |                     |                |                 |
|              | AVZ1               | EU-West-1a    |                     | 10.15.0.0/24   |                 |
|              | AVZ1               |               | Private Subnet      |                | 10.15.0.0/25    |
|              | AVZ1               |               | Public Subnet       |                | 10.15.0.128/26  |
|              | AVZ1               |               | Spare Subnet        |                |                 |
|              |                    |               |                     |                |                 |
|              | AVZ2               | EU-West-1b    |                     | 10.15.1.0/24   |                 |
|              | AVZ1               |               | Private Subnet      |                | 10.15.1.0/25    |
|              | AVZ1               |               | Public Subnet       |                | 10.15.1.128/26  |
|              | AVZ2               |               | Spare Subnet        |                |                 |


### Creating subnets in Avaiability Zone - AVZ1
```sh
EUWest1a_PvtSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block 10.15.0.0/25 --availability-zone eu-west-1a --query 'Subnet.SubnetId' --output text)
EUWest1a_PubSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block 10.15.0.128/26 --availability-zone eu-west-1a --query 'Subnet.SubnetId' --output text)
EUWest1a_SpareSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block XX.XX.XX./XX --availability-zone eu-west-1a --query 'Subnet.SubnetId' --output text)
```
##### Tag the subnet ID's for Avaiability Zone - AVZ1
```sh

aws ec2 create-tags --resources "$EUWest1a_PvtSubnetID" --tags 'Key=Name,Value=az1-eu-west-1a-pvt-Subnet'
aws ec2 create-tags --resources "$EUWest1a_PubSubnetID" --tags 'Key=Name,Value=az1-eu-west-1a-pub-Subnet'
aws ec2 create-tags --resources "$EUWest1a_SpareSubnetID" --tags 'Key=Name,Value=az1-eu-west-1a-Spare-Subnet'

```

### Creating subnets in Avaiability Zone - AVZ2
```sh
EUWest1b_DbSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block 10.15.1.0/25 --availability-zone eu-west-1b --query 'Subnet.SubnetId' --output text)
EUWest1b_WebSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block 10.15.1.128/25 --availability-zone eu-west-1b --query 'Subnet.SubnetId' --output text)
EUWest1b_SpareSubnetID=$(aws ec2 create-subnet --vpc-id "$vpcID" --cidr-block XX.XX.XX./XX --availability-zone eu-west-1b --query 'Subnet.SubnetId' --output text)
```
##### Tag the subnet ID's for Avaiability Zone - AVZ2
```sh
aws ec2 create-tags --resources "$EUWest1b_PvtSubnetID" --tags 'Key=Name,Value=az1-eu-west-1c-Pvt-Subnet'
aws ec2 create-tags --resources "$EUWest1b_PubSubnetID" --tags 'Key=Name,Value=az1-eu-west-1c-Pub-Subnet'
aws ec2 create-tags --resources "$EUWest1b_SpareSubnetID" --tags 'Key=Name,Value=az1-eu-west-1c-Spare-Subnet'
```

### Configuring the Route Table
Each subnet needs to have a route table associated with it to specify the routing of its outbound traffic. By default every subnet inherits the default VPC route table which allows for intra-VPC communication only.

The following adds a route table to our subnet that allows traffic not meant for an instance inside the VPC to be routed to the internet through our earlier created internet gateway.

```sh
routeTableID=$(aws ec2 create-route-table --vpc-id "$vpcID" --query 'RouteTable.RouteTableId' --output text)

aws ec2 create-route --route-table-id "$routeTableID" --destination-cidr-block 0.0.0.0/0 --gateway-id "$internetGatewayId"
aws ec2 associate-route-table --route-table-id "$routeTableID" --subnet-id "$EUWest1a_WebSubnetID"
aws ec2 associate-route-table --route-table-id "$routeTableID" --subnet-id "$EUWest1b_WebSubnetID"
```

### Creating a security group
 - Group Name - `WebSecGrp`
 - Description - `Web Security Group for Server's`

```sh
WebSecGrpID=$(aws ec2 create-security-group --group-name WebSecGrp \
            --description "Security Group for Web servers" \
            --vpc-id "$vpcID" \
            --output text)
```

#### Add a rule that allows inbound SSH, HTTP, HTTP traffic ( from any source )

```sh
aws ec2 authorize-security-group-ingress --group-id "$WebSecGrpID" --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$WebSecGrpID" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$WebSecGrpID" --protocol tcp --port 443 --cidr 0.0.0.0/0
```

>When you specify a security group for a nondefault VPC to the CLI or the API actions, you must use the security group ID and not the security group name to identify the security group.
