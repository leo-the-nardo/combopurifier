package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

type WebhookHandler struct {
	SQSClient *sqs.Client
	QueueURL  string
}

// Main function
func main() {
	// Initialize AWS configuration
	ctx := context.Background()
	cfg, err := config.LoadDefaultConfig(ctx)
	if err != nil {
		log.Fatalf("Failed to load AWS SDK config: %v", err)
	}

	// Create an SQS client
	sqsClient := sqs.NewFromConfig(cfg)

	// Retrieve the SQS queue URL from environment variables
	queueURL := os.Getenv("SQS_QUEUE_URL")
	if queueURL == "" {
		log.Fatal("SQS_QUEUE_URL environment variable is not set")
	}
	// Initialize the handler with dependencies
	handler := &WebhookHandler{
		SQSClient: sqsClient,
		QueueURL:  queueURL,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("POST /minio-webhook", handler.Webhook)

	server := &http.Server{
		Addr:    ":8080",
		Handler: mux,
	}

	log.Println("Server started on port 8080...")
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("Server error: %v", err)
	}
}

// Webhook handler method
func (h *WebhookHandler) Webhook(w http.ResponseWriter, r *http.Request) {
	// Decode the incoming JSON payload
	var event S3Event
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	// Process the event
	if err := h.processEvent(r.Context(), event); err != nil {
		log.Printf("Error processing event: %v", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
}

// Process the event and send to SQS
func (h *WebhookHandler) processEvent(ctx context.Context, event S3Event) error {
	// Marshal the event to JSON
	messageBody, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Send the message to SQS
	input := &sqs.SendMessageInput{
		MessageBody: aws.String(string(messageBody)),
		QueueUrl:    aws.String(h.QueueURL),
	}

	if _, err := h.SQSClient.SendMessage(ctx, input); err != nil {
		return fmt.Errorf("failed to send message to SQS: %w", err)
	}

	log.Println("Message sent to SQS successfully.")
	return nil
}

// Define the S3 event structs
type S3Event struct {
	Records []Record `json:"Records"`
}

type Record struct {
	EventVersion      string            `json:"eventVersion"`
	EventSource       string            `json:"eventSource"`
	AWSRegion         string            `json:"awsRegion"`
	EventTime         string            `json:"eventTime"`
	EventName         string            `json:"eventName"`
	UserIdentity      UserIdentity      `json:"userIdentity"`
	RequestParameters RequestParameters `json:"requestParameters"`
	ResponseElements  ResponseElements  `json:"responseElements"`
	S3                S3Entity          `json:"s3"`
}

type UserIdentity struct {
	PrincipalID string `json:"principalId"`
}

type RequestParameters struct {
	SourceIPAddress string `json:"sourceIPAddress"`
}

type ResponseElements struct {
	XAmzRequestID string `json:"x-amz-request-id"`
	XAmzID2       string `json:"x-amz-id-2"`
}

type S3Entity struct {
	S3SchemaVersion string   `json:"s3SchemaVersion"`
	ConfigurationID string   `json:"configurationId"`
	Bucket          Bucket   `json:"bucket"`
	Object          S3Object `json:"object"`
}

type Bucket struct {
	Name          string        `json:"name"`
	OwnerIdentity OwnerIdentity `json:"ownerIdentity"`
	Arn           string        `json:"arn"`
}

type OwnerIdentity struct {
	PrincipalID string `json:"principalId"`
}

type S3Object struct {
	Key       string `json:"key"`
	Size      int    `json:"size"`
	ETag      string `json:"eTag"`
	VersionID string `json:"versionId"`
	Sequencer string `json:"sequencer"`
}
