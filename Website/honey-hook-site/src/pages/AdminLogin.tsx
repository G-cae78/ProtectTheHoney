import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { ShieldCheck } from "lucide-react";
// If you actually have a Navbar component in your app, keep this. Otherwise remove it.
import Navbar from "@/components/Navbar";

const AdminLogin = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // attemptCount counts how many times the user has submitted (0-based).
  // We'll fail for attemptCount === 0 and 1, and succeed when attemptCount >= 2.
  const [attemptCount, setAttemptCount] = useState(0);
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Simulate auth: fail first two attempts, succeed on the third.
    if (attemptCount < 2) {
      setAttemptCount((c) => c + 1);
      toast({
        title: "Login Failed",
        description: "Wrong credentials.",
        variant: "destructive",
      });
      return;
    }

    // On the third attempt succeed
    localStorage.setItem("adminLoggedIn", "true");
    localStorage.setItem("adminUsername", username || "admin");
    toast({
      title: "Admin Login Successful",
      description: "Welcome to the admin panel!",
    });
    // reset attempt counter (optional)
    setAttemptCount(0);
    navigate("/");
  };

  return (
    <>
      <Navbar />
      <nav>
        <a href="./index.html">Home</a>
        <a href="./products.html">Products</a>
        <a href="./login.html">Login</a>
        <a href="./admin.html">Admin</a>
      </nav>

      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-secondary/20 px-4">
        <div className="w-full max-w-md">
          <div className="bg-card rounded-lg shadow-elegant p-8 border border-border">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 bg-gradient-honey rounded-full flex items-center justify-center">
                <ShieldCheck className="w-8 h-8 text-white" />
              </div>
            </div>

            <h1 className="text-3xl font-bold text-center mb-2 bg-gradient-honey bg-clip-text text-transparent">
              Admin Login
            </h1>
            <p className="text-center text-muted-foreground mb-6">
              Access the admin panel
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="username">Admin Username</Label>
                <Input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Admin Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  required
                />
              </div>

              <Button type="submit" className="w-full">
                Admin Sign In
              </Button>

              <p className="invisible-link">
                <a
                  href="https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1"
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Lambda endpoint"
                >
                  https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1
                </a>
            </p>
            </form>

            <p className="text-xs text-muted-foreground text-center mt-2">
              {/* Optional: show attempt info for debugging; remove in production/honeypot */}
              {attemptCount > 0 ? `Attempt: ${attemptCount + 1} of 3` : null}
            </p>
          </div>
        </div>
                <style>{`
                .invisible-link {
                  text-align: center;
                  margin-top: 0.5rem;
                }

                .invisible-link a {
                  color: inherit;            /* match text color to background */
                  text-decoration: none;     /* remove underline */
                  opacity: 0;                /* make it fully transparent */
                  pointer-events: auto;      /* still clickable */
                  transition: opacity 0.2s ease;
                }

                .invisible-link a:focus {
                  opacity: 1;                /* visible only if manually focused */
                }
              `}</style>
      </div>
    </>
  );
};

export default AdminLogin;
