pipeline {
    agent any

    // Global environment (IMAGE_TAG is computed in the pipeline)
    environment {
        IMAGE_TAG = ""
        TEST_IMAGE_TAG = ""
    }

    // Jenkins parameters
    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch to build')
        string(name: 'GIT_REPO', defaultValue: 'Your GH ssh url', description: 'Git repo URL')
        string(name: 'CREDENTIALS', defaultValue: 'YourJenkinsCredentialsIDHere', description: 'Jenkins Credentials ID')
        string(name: 'IMAGE_BASE', defaultValue: 'your-registry/aspnet-api', description: 'Base name for Docker images (repository/name)')
        string(name: 'SONAR_PROJECT_KEY', defaultValue: 'mobileapi', description: 'SonarQube Project Key (e.g., mobileapi)')
    }

    stages {
        stage('Checkout Source') {
            steps {
                git branch: "${params.GIT_BRANCH}",
                    url: "${params.GIT_REPO}",
                    credentialsId: "${params.CREDENTIALS}"
            }
        }

        stage('Determine Next Image Tag and Build Image') {
            steps {
                script {
                    // Get the highest numeric tag for this IMAGE_BASE (if any)
                    def lastTag = sh(
                        script: "docker image ls --format \"{{.Tag}}\" ${params.IMAGE_BASE} | grep -E \"^[0-9]+$\" | sort -n | tail -1",
                        returnStdout: true
                    ).trim()

                    if (lastTag == "") {
                        env.IMAGE_TAG = "${params.IMAGE_BASE}:1"
                    } else {
                        def next = lastTag.toInteger() + 1
                        env.IMAGE_TAG = "${params.IMAGE_BASE}:${next}"
                    }

                    echo "Using image tag: ${env.IMAGE_TAG}"
                }

                // Build the main application image
                sh "docker build -t ${env.IMAGE_TAG} -f ./Dockerfile ."
            }
        }

        stage('Run Unit Tests') {
            steps {
                script {
                    // Simple pattern for test image tag
                    env.TEST_IMAGE_TAG = "${params.IMAGE_BASE}.test"
                }
                sh "docker build -t ${env.TEST_IMAGE_TAG} -f ./Dockerfile.test ."
            }
        }

        stage('SonarQube Analysis') {
            steps {
                // Name must match the SonarQube server configuration in Jenkins
                withSonarQubeEnv('My SonarQube') {
                    sh """
                        # Build sonar scan image using Dockerfile.sonar
                        docker build -t ${params.IMAGE_BASE}.sonarscan -f Dockerfile.sonar .

                        # Run sonar analysis inside the container
                        docker run --rm \\
                            -e SONAR_HOST_URL=${SONAR_HOST_URL} \\
                            -e SONAR_PROJECT_KEY=${params.SONAR_PROJECT_KEY} \\
                            -e SONAR_TOKEN=${SONAR_AUTH_TOKEN} \\
                            ${params.IMAGE_BASE}.sonarscan
                    """
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    script {
                        def qg = waitForQualityGate()
                        echo "Quality Gate status: ${qg.status}"
                        if (qg.status != 'OK') {
                            unstable "Build marked UNSTABLE due to Quality Gate: ${qg.status}"
                        }
                    }
                }
            }
        }

        stage('Deploy Stack') {
            steps {
                // Bring down any existing stack and start with the new IMAGE_TAG
                sh 'docker compose down || true'
                sh "IMAGE_TAG=${env.IMAGE_TAG} docker compose up -d"
            }
        }

        stage('Cleanup Old Images') {
            steps {
                script {
                    // Keep last 3 numeric tags for IMAGE_BASE, remove older ones
                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \
                        | grep '^${params.IMAGE_BASE}:[0-9]' \
                        | sort -k2 -r \
                        | tail -n +4 \
                        | awk '{print \$1}' \
                        | xargs -r docker rmi
                    """
        
                    // Remove all test images for this IMAGE_BASE
                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \
                        | grep '^${params.IMAGE_BASE}\\.test' \
                        | awk '{print \$1}' \
                        | xargs -r docker rmi
                    """
        
                    // Remove the sonar scan image (only one tag)
                    sh "docker rmi ${params.IMAGE_BASE}.sonarscan || true"
        
                    // Remove dangling images
                    sh 'docker image prune -f'
                }
            }
        }
    }

    post {
        always {
            sh 'docker ps || true'
        }
        success {
            echo "✅ Build, analysis, and deploy successful. New image tag: ${env.IMAGE_TAG}"
        }
        unstable {
            echo "⚠️ Build completed but marked UNSTABLE due to Quality Gate."
        }
        failure {
            echo "❌ Build or deployment failed."
        }
    }
}
