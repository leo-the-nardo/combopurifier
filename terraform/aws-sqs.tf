# Terraform configuration
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"  # Use the latest compatible version
    }
  }
}

# AWS Provider configuration
provider "aws" {
  region = "us-east-2"  # Change to your desired AWS region
}

#############################################
# Create Primary SQS Queue and DLQ
#############################################

# Create the Dead Letter Queue (DLQ)
resource "aws_sqs_queue" "input_notification_dlq" {
  name = "input-notification-dlq"

  # Optional: Set DLQ-specific configurations here
}

# Create the Primary SQS Queue with Redrive Policy pointing to the DLQ
resource "aws_sqs_queue" "input_notification" {
  name = "input-notification"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.input_notification_dlq.arn
    maxReceiveCount     = 5  # Adjust based on your retry requirements
  })
}

# Output the Primary SQS queue URL
output "sqs_queue_url" {
  value = aws_sqs_queue.input_notification.id
}

# Output the DLQ SQS queue URL
output "sqs_dlq_queue_url" {
  value = aws_sqs_queue.input_notification_dlq.id
}

#############################################
# IAM Policy for Both Publisher and Consumer
#############################################

# IAM policy with send and receive permissions for both queues
resource "aws_iam_policy" "sqs_access_policy" {
  name        = "sqs-access-policy"
  description = "Policy to allow sending and receiving messages to/from SQS queues"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "AllowSendReceiveMessages",
        Effect   = "Allow",
        Action   = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ],
        Resource = [
          aws_sqs_queue.input_notification.arn,
          aws_sqs_queue.input_notification_dlq.arn  # Added DLQ ARN
        ]
      }
    ]
  })
}

#############################################
# IAM User for Publisher Application
#############################################

# Create an IAM user for the publisher application
resource "aws_iam_user" "publisher_user" {
  name = "publisher-app-user"
}

# Attach the SQS access policy to the publisher IAM user
resource "aws_iam_user_policy_attachment" "publisher_user_policy_attachment" {
  user       = aws_iam_user.publisher_user.name
  policy_arn = aws_iam_policy.sqs_access_policy.arn
}

# Create access keys for the publisher IAM user
resource "aws_iam_access_key" "publisher_user_key" {
  user = aws_iam_user.publisher_user.name

  # PGP encryption for the secret access key (optional but recommended)
  # pgp_key = file("path/to/your/public_key.asc")
}

# Output the access key ID and secret access key for publisher (handle with care)
output "publisher_aws_access_key_id" {
  value       = aws_iam_access_key.publisher_user_key.id
  description = "AWS Access Key ID for the publisher IAM user"
}

output "publisher_aws_secret_access_key" {
  value       = aws_iam_access_key.publisher_user_key.secret
  description = "AWS Secret Access Key for the publisher IAM user"

  # Sensitive output to prevent it from being displayed in CLI output
  sensitive = true
}

#############################################
# IAM User for Consumer Application
#############################################

# Create an IAM user for the consumer application
resource "aws_iam_user" "consumer_user" {
  name = "consumer-app-user"
}

# Attach the SQS access policy to the consumer IAM user
resource "aws_iam_user_policy_attachment" "consumer_user_policy_attachment" {
  user       = aws_iam_user.consumer_user.name
  policy_arn = aws_iam_policy.sqs_access_policy.arn
}

# Create access keys for the consumer IAM user
resource "aws_iam_access_key" "consumer_user_key" {
  user = aws_iam_user.consumer_user.name

  # PGP encryption for the secret access key (optional but recommended)
  # pgp_key = file("path/to/your/public_key.asc")
}

# Output the access key ID and secret access key for consumer (handle with care)
output "consumer_aws_access_key_id" {
  value       = aws_iam_access_key.consumer_user_key.id
  description = "AWS Access Key ID for the consumer IAM user"
}

output "consumer_aws_secret_access_key" {
  value       = aws_iam_access_key.consumer_user_key.secret
  description = "AWS Secret Access Key for the consumer IAM user"

  # Sensitive output to prevent it from being displayed in CLI output
  sensitive = true
}
