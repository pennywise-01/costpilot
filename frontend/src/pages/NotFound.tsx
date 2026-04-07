import { useNavigate } from 'react-router-dom';
import { Result, Button } from 'antd';

const NotFound: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Result
      status="404"
      title="Page Not Found"
      subTitle="The page you're looking for doesn't exist"
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          Back to Dashboard
        </Button>
      }
    />
  );
};

export default NotFound;
