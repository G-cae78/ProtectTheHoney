import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { ShieldCheck } from "lucide-react";

const AdminLogin = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Basic admin authentication (in production, this should be server-side)
    if (username === "admin" && password === "admin123") {
      localStorage.setItem("adminLoggedIn", "true");
      localStorage.setItem("adminUsername", username);
      toast({
        title: "Admin Login Successful",
        description: "Welcome to the admin panel!",
      });
      navigate("/");
    } else {
      toast({
        title: "Login Failed",
        description: "Invalid admin credentials.",
        variant: "destructive",
      });
    }
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
          </form>
          
          <p className="text-xs text-muted-foreground text-center mt-4">
            Default: admin / admin123
          </p>
        </div>
      </div>
    </div>
    </>
  );
};

export default AdminLogin;
