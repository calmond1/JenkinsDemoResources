pipeline {
    agent any

    // Global environment (computed in the pipeline)
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

                sh "docker build -t ${env.IMAGE_TAG} -f ./Dockerfile ."
            }
        }

        stage('Run Unit Tests') {
            steps {
                script {
                    env.TEST_IMAGE_TAG = "${params.IMAGE_BASE}.test"
                }

                sh """
                  docker build -t ${env.TEST_IMAGE_TAG} -f ./Dockerfile.test .

                  rm -rf TestResults
                  mkdir -p TestResults

                  docker run --rm \\
                    -v \$PWD/TestResults:/src/TestResults \\
                    ${env.TEST_IMAGE_TAG}
                """
                
                // Requires the junit plugin in Jenkins
                junit 'TestResults/*.xml'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('My SonarQube') {
                    sh """
                        docker build -t ${params.IMAGE_BASE}.sonarscan -f Dockerfile.sonar .

                        docker run --rm \\
                            -e SONAR_HOST_URL=${SONAR_HOST_URL} \\
                            -e SONAR_PROJECT_KEY=${params.SONAR_PROJECT_KEY} \\
                            -e SONAR_TOKEN=${SONAR_AUTH_TOKEN} \\
                            ${params.IMAGE_BASE}.sonarscan
                    """
                }
            }
        }

        // Only enforce Quality Gate for main branch
        stage('Quality Gate') {
            when { branch 'main' }  // Feature branches still run analysis, but don't enforce gates
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

        // Only deploy when building from main branch
        stage('Deploy Stack') {
            when { branch 'main' }  // Prevents deployment from feature/test branches
            steps {
                sh 'docker compose down || true'
                sh "IMAGE_TAG=${env.IMAGE_TAG} docker compose up -d"
            }
        }

        stage('Cleanup Old Images') {
            steps {
                script {
                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \\
                        | grep '^${params.IMAGE_BASE}:[0-9]' \\
                        | sort -k2 -r \\
                        | tail -n +4 \\
                        | awk '{print \$1}' \\
                        | xargs -r docker rmi
                    """

                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \\
                        | grep '^${params.IMAGE_BASE}\\.test' \\
                        | awk '{print \$1}' \\
                        | xargs -r docker rmi
                    """

                    sh "docker rmi ${params.IMAGE_BASE}.sonarscan || true"

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
