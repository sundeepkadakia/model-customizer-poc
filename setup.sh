#
# verify the active account and project
#   
firebase login:list
firebase use
#
# firestore.rules does not exist, initialize it:
#
firebase init firestore
#
# Deploy the Firestore security rules to the Firebase project
#
firebase deploy \
  --only firestore:rules \
  --project modelcustomizerplatform
#
# Build and Deploy the Firebase Cloud Functions to the Firebase project
#
cd frontend
npm run build
cd ..
firebase deploy --only hosting
#
# Grant the service account permission to view Firebase Authentication users
#
gcloud projects add-iam-policy-binding modelcustomizerplatform \
  --member="serviceAccount:model-customizer-api@modelcustomizerplatform.iam.gserviceaccount.com" \
  --role="roles/firebaseauth.viewer"
