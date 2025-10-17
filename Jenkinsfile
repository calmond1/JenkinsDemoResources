pipeline {
    agent any

    environment {
        IMAGE_BASE = "ChangeMe"
    }

    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch to build')
        string(name: 'GIT_REPO', defaultValue: 'Your GH ssh url', description: 'Git repo URL')
        string(name: 'CREDENTIALS', defaultValue: 'YourJenkinsCredentialsIDHere', description: 'Jenkins Credentials ID')
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
                    // Get the highest numeric tag, if any
                    def lastTag = sh(
                        script: 'docker image ls --format "{{.Tag}}" ${IMAGE_BASE} | grep -E "^[0-9]+$" | sort -n | tail -1',
                        returnStdout: true
                    ).trim()

                    if (lastTag == "") {
                        env.IMAGE_TAG = "${IMAGE_BASE}:1"
                    } else {
                        def next = lastTag.toInteger() + 1
                        env.IMAGE_TAG = "${IMAGE_BASE}:${next}"
                    }

                    echo "Using image tag: ${env.IMAGE_TAG}"
                }
                sh "docker build -t ${env.IMAGE_TAG} -f ./Dockerfile ."
            }
        }
        
        stage('Run Unit Tests') {
            steps {
                sh "docker build -t ${IMAGE_BASE}.test.${env.IMAGE_TAG} -f ./Dockerfile.test ."
            }
        }
        
        stage('Deploy Stack') {
            steps {
                sh 'docker compose down || echo . >/dev/null'
                sh "IMAGE_TAG=${env.IMAGE_TAG} docker compose up -d"
            }
        }

        //stage('Cleanup Old Images') {
        //    steps {
        //        // You can move the Cleanup Old Images into a different pipeline and trigger it from here instead
        //        build job: 'YourJenkinsCleanupProjectName', wait: false
        //    }
        //}
        stage('Cleanup Old Images') {
            steps {
                script {
                    // Keep last 3 numeric tags, delete the rest
                    sh """
					    docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" | grep '^${env.IMAGE_BASE}*.[0-9]' \
					    | sort -k2 -r | tail -n +4 | awk '{print \$1}' | xargs -r docker rmi
					"""
                    sh '''
                       docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" | grep '^${env.IMAGE_BASE}*.test' \
                        | awk '{print $1}' | xargs -r docker rmi
                    '''
                    sh 'docker image prune -f'
                }
            }
        }
    }

    post {
	    always {
			sh 'docker ps'
		}
        success {
            echo "✅ Build and deploy successful, new image tag is ${env.IMAGE_TAG}"
        }
        failure {
            echo "❌ Build or deploy failed"
        }
    }
}
