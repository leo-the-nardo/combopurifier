kubectl create namespace  airflow
---
# install the postgres-operator
helm repo add postgres-operator-charts https://opensource.zalando.com/postgres-operator/charts/postgres-operator
helm install postgres-operator postgres-operator-charts/postgres-operator \
  --namespace airflow \
  --set configKubernetes.namespace=airflow
---
2. Create Kubernetes Secret for the airflow User

The operator expects a secret named pguser-airflow containing the password under the key password.

Create the Secret:

bash

export AIRFLOW_DB_PASSWORD="<your_airflow_db_password>"

kubectl create secret generic pguser-airflow \
  --namespace airflow \
  --from-literal=password="$AIRFLOW_DB_PASSWORD"---

kubectl apply -f airflow-postgres.yaml -n airflow
---


Create a Secret for Airflow Configuration

Generate a Fernet key and store it along with other Airflow secrets.

bash

FERNET_KEY=$(openssl rand -base64 32)
kubectl create secret generic airflow-secrets \
  --from-literal=fernet-key="$FERNET_KEY" \
  --from-literal=webserver-secret-key="$(openssl rand -base64 32)" \
  --namespace airflow

Create a Secret for GitHub Access (if using a private repo)

If your DAGs repository is private, create a Kubernetes Secret with your Git credentials.

bash

kubectl create secret generic git-credentials \
  --from-literal=username='<your-github-username>' \
  --from-literal=password='<your-github-token>' \
  --namespace airflow

helm repo add apache-airflow https://airflow.apache.org
helm repo update

Apply the RBAC policies:
kubectl apply -f airflow-rbac.yaml

Step 6: Deploy Airflow
Install Airflow using Helm with the custom values.yaml:
Note:
    Replace <your-webserver-password> with a secure password for the Airflow web UI admin user.
    The fernetKey and webserverPassword are set via Helm's --set flag to avoid hardcoding them in YAML files.

helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --values airflow-values.yaml \
  --set fernetKey="$FERNET_KEY" \
  --set webserverPassword="<your-webserver-password>"


Check Airflow Pods

bash

kubectl get pods -n airflow

Ensure that the airflow-webserver and airflow-scheduler Pods are running.
Verify DAG Synchronization

Check the logs of the git-sync sidecar container:

bash

kubectl logs deployment/airflow-scheduler -c git-sync -n airflow

Ensure that the DAGs are being synchronized from your GitHub repository.
Access the Airflow Web UI

Forward the webserver port to your local machine:

bash

kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow

Access the web UI at http://localhost:8080 and log in with:

    Username: admin
    Password: The password you set during the Helm install.