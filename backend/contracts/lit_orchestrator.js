import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import vm from 'vm';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read arguments
const args = process.argv.slice(2);
if (args.length < 1) {
    console.error("Usage: node lit_orchestrator.js <base64_json_payload>");
    process.exit(1);
}

const payloadStr = Buffer.from(args[0], 'base64').toString('utf8');
const payload = JSON.parse(payloadStr);

const { 
    amount, 
    sub_task, 
    reputation, 
    from_wallet, 
    to_wallet, 
    dataToSign 
} = payload;

// Load Lit Action JS Action
const litActionCode = fs.readFileSync(path.join(__dirname, 'ows_policy.js'), 'utf8');

const main = async () => {
    // If real LIT_PKP_PUBLIC_KEY is provided in env, we could use LitNodeClient here.
    // For local hackathon development, we EMULATE the Lit Action execution environment.
    
    let simulatedResponse = null;
    let simulatedSignature = null;
    
    // Create Lit emulation object
    const Lit = {
        Actions: {
            setResponse: ({ response }) => {
                simulatedResponse = response;
            },
            signEcdsa: ({ toSign, publicKey, sigName }) => {
                // Mock signing process in devnet mode
                const mockSig = "0x" + Buffer.from(toSign + Date.now()).toString('hex').slice(0, 130);
                simulatedSignature = mockSig;
            }
        }
    };

    // Construct VM Sandbox to run Lit Action cleanly
    const sandbox = {
        Lit,
        amount,
        sub_task,
        reputation,
        from_wallet,
        to_wallet,
        dataToSign: dataToSign || "mock_hash_to_sign",
        publicKey: process.env.LIT_PKP_PUBLIC_KEY || "mock_pkp_key",
        sigName: "ows_signature",
        console // Allow logging mapping
    };

    vm.createContext(sandbox);
    
    try {
        const script = new vm.Script(litActionCode);
        script.runInContext(sandbox); // Natively executes the JS Action
        
        let parsedResponse = {};
        if (simulatedResponse) {
            parsedResponse = JSON.parse(simulatedResponse);
        }

        console.log(JSON.stringify({
            success: true,
            policy_result: parsedResponse,
            signature: simulatedSignature
        }));

    } catch (e) {
        console.log(JSON.stringify({
            success: false,
            error: e.message
        }));
    }
};

main();
