// Everything the scouting chat bot needs, in resource group trisonics-chat:
//   az deployment group create -g trisonics-chat -f infra/main.bicep
// then publish the code with infra/deploy.sh. Rerunning is safe.
//
// Reads (not creates) the scouting Cosmos account in another resource group,
// using its read-only key: the bot can never change scouting data.

param location string = resourceGroup().location
param appName string = 'trisonics-chat'
param foundryName string = 'trisonics-foundry'
param cosmosAccountName string = 'trisonics-scouting'
param cosmosResourceGroup string = 'trisonics-scouting'

@description('Foundry deployment the bot uses (swap models by repointing it, or set this)')
param chatDeployment string = 'scout-chat'

@description('Claude deployments in Foundry. Capacity = thousands of tokens per minute.')
param modelDeployments array = [
  { name: 'scout-chat', model: 'claude-sonnet-5-5', version: '2', capacity: 80 }
  { name: 'scout-chat-haiku', model: 'claude-haiku-5-5', version: '2', capacity: 80 }
]

@description('Anthropic asks for these when a Claude model is deployed')
param modelProviderData object = {
  organizationName: 'TriSonics FRC Team 4003'
  industry: 'education'
  countryCode: 'US'
}

@description('Instances kept warm for Slack (0 = scale to zero, no idle cost, but the first message after a quiet spell can take a few seconds). 1 is about $5/month at 512 MB; turn it on for competition weekends.')
@minValue(0)
param alwaysReadyHttp int = 1

@allowed([ 512, 2048, 4096 ])
param instanceMemoryMB int = 512

@secure()
@description('TBA read key, for the history refresh (pass it: tbaKey=$TBA_KEY from trisonics-api/setenv)')
param tbaKey string = ''

@description('History refresh timer: on/off and NCRONTAB schedule. Off until competition season.')
param historyRefreshEnabled bool = false
param historyRefreshSchedule string = '0 5 * * * *'

param budgetAmount int = 100
param budgetEmail string = 'justin.buist@gmail.com'
@description('First day of a month; the budget repeats monthly from here')
param budgetStart string = '2026-11-01'

var tags = { app: appName }
var storageName = toLower(replace('${appName}st', '-', ''))

// --- Foundry (model hosting) ---

resource foundry 'Microsoft.CognitiveServices/accounts@2025-10-01-preview' = {
  name: foundryName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: foundryName
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-10-01-preview' = {
  parent: foundry
  name: 'scout-chat-project'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {}
}

@batchSize(1)
resource models 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = [for d in modelDeployments: {
  parent: foundry
  name: d.name
  sku: { name: 'GlobalStandard', capacity: d.capacity }
  properties: {
    model: { format: 'Anthropic', name: d.model, version: d.version }
    #disable-next-line BCP037
    modelProviderData: modelProviderData
  }
  dependsOn: [ foundryProject ]  // one change at a time on the account
}]

// --- Function App (Flex Consumption: no cost when idle) ---

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource deployContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'deployments'
}

resource historyContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'history'
}

// One empty blob per Slack message answered, so two instances never both answer it.
resource claimsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'slack-claims'
}

// One blob per "Looking that up" placeholder until its answer lands (SlackWatchdog).
resource pendingContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'slack-pending'
}

resource queues 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource slackQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queues
  name: 'slack-events'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${appName}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${appName}-plan'
  location: location
  tags: tags
  kind: 'functionapp'
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
  scope: resourceGroup(cosmosResourceGroup)
}

var storageConn = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource site 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}deployments'
          authentication: {
            type: 'StorageAccountConnectionString'
            storageAccountConnectionStringName: 'DEPLOYMENT_STORAGE_CONNECTION_STRING'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: instanceMemoryMB
        alwaysReady: alwaysReadyHttp > 0 ? [ { name: 'http', instanceCount: alwaysReadyHttp } ] : []
      }
      runtime: { name: 'python', version: '3.13' }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: storageConn }
        { name: 'DEPLOYMENT_STORAGE_CONNECTION_STRING', value: storageConn }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
        { name: 'FOUNDRY_RESOURCE', value: foundry.name }
        { name: 'FOUNDRY_DEPLOYMENT', value: chatDeployment }
        { name: 'FOUNDRY_API_KEY', value: foundry.listKeys().key1 }
        { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
        { name: 'COSMOS_READ_KEY', value: cosmos.listKeys().primaryReadonlyMasterKey }
        { name: 'TBA_KEY', value: tbaKey }
        { name: 'HISTORY_REFRESH_SCHEDULE', value: historyRefreshSchedule }
        { name: 'AzureWebJobs.HistoryRefresh.Disabled', value: historyRefreshEnabled ? 'false' : 'true' }
      ]
    }
  }
  dependsOn: [ deployContainer, historyContainer, claimsContainer, pendingContainer, slackQueue, models ]
}

// --- Spending alert ---

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${appName}-monthly'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: '${budgetStart}T00:00:00Z', endDate: '2036-11-01T00:00:00Z' }
    notifications: {
      actual50: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 50, thresholdType: 'Actual', contactEmails: [ budgetEmail ] }
      actual100: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 100, thresholdType: 'Actual', contactEmails: [ budgetEmail ] }
      forecast100: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 100, thresholdType: 'Forecasted', contactEmails: [ budgetEmail ] }
    }
  }
}

output slackEventsUrl string = 'https://${site.properties.defaultHostName}/api/SlackEvents'
