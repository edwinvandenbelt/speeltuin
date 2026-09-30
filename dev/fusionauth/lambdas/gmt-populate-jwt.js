// Zet de applicatierollen en een leesbare naam in het token.
//
// FusionAuth stopt rollen standaard wél in het access token, maar niet in het
// id_token.  gmt_auth.py leest het id_token, dus kopiëren we ze hier expliciet.
// Deze lambda hangt aan de GMT-applicatie als zowel access- als id-token-populate.
function populate(jwt, user, registration) {
  jwt.roles = registration.roles || [];
  jwt.email = user.email;
  jwt.name = user.fullName || user.firstName || user.username || user.email;
  jwt.preferred_username = user.username || user.email;
}
