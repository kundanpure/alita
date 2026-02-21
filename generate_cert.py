"""
Generate a self-signed SSL certificate for Alita.
Run this ONCE: python generate_cert.py
Then start the server: python main.py
"""
import subprocess, sys, os

cert_file = "cert.pem"
key_file  = "key.pem"

if os.path.exists(cert_file) and os.path.exists(key_file):
    print("✅ Certificates already exist. Run: python main.py")
    sys.exit(0)

# Try using Python's built-in ssl/cryptography to generate cert
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    import datetime, ipaddress, socket

    print("Generating self-signed SSL certificate...")

    # Get local IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Local IP detected: {local_ip}")

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Build certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Alita-Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Alita AI Partner"),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address(local_ip)),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256(), default_backend())
    )

    # Write cert and key
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))

    print(f"\n✅ SSL certificates generated!")
    print(f"   cert.pem — certificate")
    print(f"   key.pem  — private key")
    print(f"\nNow run: python main.py")
    print(f"\nYour local IP: {local_ip}")
    print(f"Access on phone: https://{local_ip}:8000")
    print(f"(Accept the security warning once — it's safe, it's your own cert)\n")

except ImportError:
    print("Installing required package...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    print("Done! Run this script again: python generate_cert.py")
